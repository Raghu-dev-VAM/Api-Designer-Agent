"""
Code generation router.
Sequential direct Groq API calls — one focused prompt per file group.
Steps 12+13 review every generated file for build errors, deprecated APIs,
naming standards before packaging.
"""

import asyncio
import base64
import io
import json
import logging
import re
import uuid
import zipfile
from asyncio import Queue
from typing import AsyncGenerator

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import settings
from rag_service import (
    get_data_layer_context,
    get_business_layer_context,
    get_presentation_layer_context,
    get_solution_structure_context,
    get_full_context,
    get_naming_rules,
    get_folder_rules,
    get_build_rules,
    get_data_layer_slim,
    get_business_layer_slim,
    get_presentation_layer_slim,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/codegen", tags=["codegen"])

TOTAL_STEPS = 13
_job_queues: dict[str, Queue] = {}
_job_artifacts: dict[str, dict] = {}  # Store pre/post review artifacts
_job_incremental_files: dict[str, dict[str, str]] = {}  # Store files as they're generated


# -- Request / Response --------------------------------------------------------
class CodeGenRequest(BaseModel):
    open_api_yaml: str
    project_name: str = "GeneratedApi"
    llm_provider: str = "groq"
    include_tests: bool = False


class CodeGenStartResponse(BaseModel):
    job_id: str
    stream_url: str


# -- SSE -----------------------------------------------------------------------
def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _stream_queue(job_id: str) -> AsyncGenerator[str, None]:
    q = _job_queues.get(job_id)
    if not q:
        yield _sse("error", {"message": "Job not found"})
        return
    while True:
        try:
            msg = await asyncio.wait_for(q.get(), timeout=600)
            yield msg
            if '"event":"done"' in msg or '"event":"error"' in msg:
                break
        except asyncio.TimeoutError:
            yield _sse("error", {"message": "Job timed out"})
            break
    _job_queues.pop(job_id, None)


# -- Fence stripping ----------------------------------------------------------
def _strip_fences(text: str) -> str:
    """Remove ALL markdown code fences and artifacts from any LLM response."""
    text = text.strip()
    # Remove opening fence line (```csharp, ```json, ```xml, ``` etc)
    text = re.sub(r'^```[a-zA-Z]*\s*\n', '', text)
    # Remove closing fence line
    text = re.sub(r'\n```\s*$', '', text)
    # Remove any remaining standalone fence lines in the middle
    text = re.sub(r'^```[a-zA-Z]*\s*$', '', text, flags=re.MULTILINE)
    # Remove trailing markdown headers (### , ## , # ) that LLMs sometimes append
    text = re.sub(r'\n#{1,6}\s*$', '', text)
    # Remove trailing ### or --- separators
    text = re.sub(r'\n[#\-=]{2,}\s*$', '', text)
    return text.strip()


# -- File extraction -----------------------------------------------------------
def _extract_files(text: str) -> dict[str, str]:
    files: dict[str, str] = {}
    pattern = re.compile(
        r"===\s*FILE:\s*(.+?)\s*===\s*(?:```[a-zA-Z]*)?\s*\n(.*?)===\s*END FILE\s*===",
        re.DOTALL,
    )
    for match in pattern.finditer(text):
        path = match.group(1).strip()
        code = _strip_fences(match.group(2))
        # Remove any trailing markdown artifacts (###, ---, ===)
        code = re.sub(r'\n[#\-=]{2,}\s*$', '', code).rstrip()
        # Remove leading LLM commentary lines (// Not generating..., // Skip..., etc.)
        code = re.sub(r'^(\s*//[^\n]*\n)*(?=\s*(using|namespace|<|\[|public|internal|global))', '', code)
        if path and code.strip():
            files[path] = code.strip()
    return files


def _build_zip(files: dict[str, str], project_name: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            zf.writestr(f"{project_name}/{path}", content)
    return buf.getvalue()


def _ensure_sln_endproject(content: str) -> str:
    lines = content.splitlines()
    output: list[str] = []
    in_project = False
    has_end = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Project("):
            if in_project and not has_end:
                output.append("EndProject")
            in_project = True
            has_end = False
        if in_project and stripped == "EndProject":
            has_end = True
        output.append(line)

    if in_project and not has_end:
        output.append("EndProject")

    return "\n".join(output)


# -- Deterministic solution file generator (no LLM needed) --------------------
def _generate_sln(project_name: str, include_tests: bool) -> str:
    """Generate a valid .sln file deterministically — never rely on LLM for this."""
    # GUIDs for project type (C# class library / web app)
    csproj_type = "{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}"
    data_guid = "{" + str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{project_name}.Data")).upper() + "}"
    biz_guid = "{" + str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{project_name}.Business")).upper() + "}"
    pres_guid = "{" + str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{project_name}.Presentation")).upper() + "}"
    test_guid = "{" + str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{project_name}.Tests")).upper() + "}"

    projects = [
        (f"{project_name}.Data", f"{project_name}.Data/{project_name}.Data.csproj", data_guid),
        (f"{project_name}.Business", f"{project_name}.Business/{project_name}.Business.csproj", biz_guid),
        (f"{project_name}.Presentation", f"{project_name}.Presentation/{project_name}.Presentation.csproj", pres_guid),
    ]
    if include_tests:
        projects.append((f"{project_name}.Tests", f"{project_name}.Tests/{project_name}.Tests.csproj", test_guid))

    lines = [
        "",
        "Microsoft Visual Studio Solution File, Format Version 12.00",
        "# Visual Studio Version 17",
        "VisualStudioVersion = 17.8.34330.188",
        "MinimumVisualStudioVersion = 10.0.40219.1",
    ]
    for name, path, guid in projects:
        lines.append(f'Project("{csproj_type}") = "{name}", "{path}", "{guid}"')
        lines.append("EndProject")

    lines.append("Global")
    lines.append("\tGlobalSection(SolutionConfigurationPlatforms) = preSolution")
    lines.append("\t\tDebug|Any CPU = Debug|Any CPU")
    lines.append("\t\tRelease|Any CPU = Release|Any CPU")
    lines.append("\tEndGlobalSection")
    lines.append("\tGlobalSection(ProjectConfigurationPlatforms) = postSolution")
    for _, _, guid in projects:
        lines.append(f"\t\t{guid}.Debug|Any CPU.ActiveCfg = Debug|Any CPU")
        lines.append(f"\t\t{guid}.Debug|Any CPU.Build.0 = Debug|Any CPU")
        lines.append(f"\t\t{guid}.Release|Any CPU.ActiveCfg = Release|Any CPU")
        lines.append(f"\t\t{guid}.Release|Any CPU.Build.0 = Release|Any CPU")
    lines.append("\tEndGlobalSection")
    lines.append("EndGlobal")
    lines.append("")
    return "\n".join(lines)


# -- Deterministic .csproj generators ------------------------------------------
def _generate_data_csproj(project_name: str) -> str:
    return f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.EntityFrameworkCore" Version="8.0.0" />
    <PackageReference Include="Microsoft.EntityFrameworkCore.SqlServer" Version="8.0.0" />
    <PackageReference Include="Microsoft.EntityFrameworkCore.InMemory" Version="8.0.0" />
    <PackageReference Include="Microsoft.EntityFrameworkCore.Tools" Version="8.0.0" />
    <PackageReference Include="Microsoft.Extensions.DependencyInjection.Abstractions" Version="8.0.0" />
    <PackageReference Include="Microsoft.Extensions.Configuration.Abstractions" Version="8.0.0" />
  </ItemGroup>
</Project>
"""


def _generate_business_csproj(project_name: str) -> str:
    return f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="AutoMapper" Version="13.0.1" />
    <PackageReference Include="FluentValidation" Version="11.3.0" />
    <PackageReference Include="Microsoft.Extensions.DependencyInjection.Abstractions" Version="8.0.0" />
    <PackageReference Include="Microsoft.Extensions.Configuration.Abstractions" Version="8.0.0" />
    <PackageReference Include="Microsoft.Extensions.Logging.Abstractions" Version="8.0.0" />
  </ItemGroup>
  <ItemGroup>
    <ProjectReference Include="../{project_name}.Data/{project_name}.Data.csproj" />
  </ItemGroup>
</Project>
"""


def _generate_presentation_csproj(project_name: str) -> str:
    return f"""<Project Sdk="Microsoft.NET.Sdk.Web">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.AspNetCore.Authentication.JwtBearer" Version="8.0.0" />
    <PackageReference Include="Swashbuckle.AspNetCore" Version="6.5.0" />
    <PackageReference Include="Serilog.AspNetCore" Version="8.0.0" />
    <PackageReference Include="Serilog.Sinks.Console" Version="5.0.0" />
    <PackageReference Include="Serilog.Sinks.File" Version="5.0.0" />
    <PackageReference Include="System.IdentityModel.Tokens.Jwt" Version="7.0.3" />
    <PackageReference Include="FluentValidation.AspNetCore" Version="11.3.0" />
  </ItemGroup>
  <ItemGroup>
    <ProjectReference Include="../{project_name}.Business/{project_name}.Business.csproj" />
  </ItemGroup>
</Project>
"""


def _generate_tests_csproj(project_name: str) -> str:
    return f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <IsPackable>false</IsPackable>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.8.0" />
    <PackageReference Include="xunit" Version="2.6.2" />
    <PackageReference Include="xunit.runner.visualstudio" Version="2.5.4" />
    <PackageReference Include="Moq" Version="4.20.70" />
    <PackageReference Include="FluentAssertions" Version="6.12.0" />
    <PackageReference Include="Microsoft.AspNetCore.Mvc.Testing" Version="8.0.0" />
    <PackageReference Include="Microsoft.EntityFrameworkCore.InMemory" Version="8.0.0" />
  </ItemGroup>
  <ItemGroup>
    <ProjectReference Include="../{project_name}.Presentation/{project_name}.Presentation.csproj" />
  </ItemGroup>
</Project>
"""

# -- Deterministic launchSettings.json generator ------------------------------
def _generate_launch_settings(project_name: str) -> str:
    return json.dumps({
        "$schema": "http://json.schemastore.org/launchsettings.json",
        "profiles": {
            project_name: {
                "commandName": "Project",
                "dotnetRunMessages": True,
                "launchBrowser": True,
                "launchUrl": "swagger",
                "applicationUrl": "https://localhost:7001;http://localhost:5001",
                "environmentVariables": {
                    "ASPNETCORE_ENVIRONMENT": "Development"
                }
            },
            "IIS Express": {
                "commandName": "IISExpress",
                "launchBrowser": True,
                "launchUrl": "swagger",
                "environmentVariables": {
                    "ASPNETCORE_ENVIRONMENT": "Development"
                }
            }
        },
        "iisSettings": {
            "windowsAuthentication": False,
            "anonymousAuthentication": True,
            "iisExpress": {
                "applicationUrl": "http://localhost:5001",
                "sslPort": 44301
            }
        }
    }, indent=2)


# -- Rate limiter for LLM calls ------------------------------------------------
import time

_last_call_time: float = 0.0
_call_count: int = 0
_MIN_CALL_INTERVAL = 3.0  # seconds between LLM calls — prevents rapid quota exhaustion


async def _rate_limit_wait(q: Queue = None, step: int = 0):
    """Minimal pacing between LLM calls."""
    global _last_call_time, _call_count
    _call_count += 1
    now = time.time()
    elapsed = now - _last_call_time
    if elapsed < _MIN_CALL_INTERVAL:
        await asyncio.sleep(_MIN_CALL_INTERVAL - elapsed)
    _last_call_time = time.time()


async def _llm(
    client: httpx.AsyncClient,
    system: str,
    user: str,
    step_label: str,
    keys: list[str],
    model: str,
    q: Queue,
    step: int,
) -> str:
    await _rate_limit_wait(q, step)
    n_keys = len(keys)

    # Full model fallback chain — ordered best to most available
    all_models = [
        model,                                        # primary (llama-3.3-70b-versatile)
        "llama-3.1-8b-instant",                       # lighter, separate quota
        "meta-llama/llama-4-scout-17b-16e-instruct",  # llama 4
        "qwen/qwen3-32b",                             # qwen fallback
        "groq/compound-mini",                         # groq compound, different quota pool
    ]
    # Deduplicate while preserving order
    seen = set()
    model_chain = [m for m in all_models if not (m in seen or seen.add(m))]

    for current_model in model_chain:
        for attempt in range(n_keys):
            api_key = keys[(_call_count + attempt) % n_keys]
            try:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": current_model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user",   "content": user},
                        ],
                        "temperature": 0.2,
                        "max_tokens": 4096,
                    },
                    timeout=60.0,
                )

                if resp.status_code == 429:
                    # Read retry-after header — wait exactly as long as Groq says
                    retry_after = resp.headers.get("retry-after", "")
                    wait = int(retry_after) if retry_after.isdigit() else 5
                    wait = min(wait, 30)  # cap at 30s
                    if attempt < n_keys - 1:
                        # More keys to try — just rotate
                        await q.put(_sse("agent_message", {
                            "agent": step_label,
                            "preview": f"[{current_model}] Key ...{api_key[-4:]} rate limited, rotating key...",
                            "step": step,
                        }))
                    else:
                        # All keys exhausted on this model — wait before trying next model
                        await q.put(_sse("agent_message", {
                            "agent": step_label,
                            "preview": f"[{current_model}] All keys rate limited, waiting {wait}s then trying next model...",
                            "step": step,
                        }))
                        await asyncio.sleep(wait)
                    continue

                if resp.status_code == 401:
                    await q.put(_sse("agent_message", {
                        "agent": step_label,
                        "preview": f"Key ...{api_key[-4:]} invalid, trying next...",
                        "step": step,
                    }))
                    continue

                if resp.status_code == 400:
                    # Model deprecated/unavailable — skip to next model entirely
                    logger.warning("[%s] 400 for model %s — skipping model", step_label, current_model)
                    break

                if resp.status_code != 200:
                    logger.warning("[%s] HTTP %d from model %s: %s", step_label, resp.status_code, current_model, resp.text[:100])
                    break

                content = resp.json()["choices"][0]["message"]["content"]
                if current_model != model:
                    await q.put(_sse("agent_message", {
                        "agent": step_label,
                        "preview": f"[fallback:{current_model}] " + content[:80].replace("\n", " "),
                        "step": step,
                    }))
                else:
                    await q.put(_sse("agent_message", {
                        "agent": step_label,
                        "preview": content[:100].replace("\n", " "),
                        "step": step,
                    }))
                return content

            except httpx.TimeoutException:
                await q.put(_sse("agent_message", {
                    "agent": step_label,
                    "preview": f"Timeout on {current_model}, trying next...",
                    "step": step,
                }))
                continue
            except RuntimeError:
                raise
            except Exception as ex:
                logger.error("LLM error on %s: %s", current_model, ex)
                continue

    raise RuntimeError(
        f"[{step_label}] All models and keys exhausted. "
        f"Tried: {', '.join(model_chain)}. "
        f"Free tier quota exceeded — please wait 1-2 minutes and retry."
    )


# -- .NET 8 Package standards (lean — full rules in knowledge/build_rules.md) --
DOTNET_PACKAGES = """
.NET 8 COMPATIBLE PACKAGES (use exactly these versions):
  Microsoft.EntityFrameworkCore 8.0.0
  Microsoft.EntityFrameworkCore.SqlServer 8.0.0
  Microsoft.EntityFrameworkCore.InMemory 8.0.0
  AutoMapper 13.0.1 (NOT 14+, NOT AutoMapper.Extensions.Microsoft.DependencyInjection)
  FluentValidation.AspNetCore 11.3.0
  Serilog.AspNetCore 8.0.0
  Swashbuckle.AspNetCore 6.5.0
  Microsoft.AspNetCore.Authentication.JwtBearer 8.0.0
  System.IdentityModel.Tokens.Jwt 7.0.3

CRITICAL:
- AutoMapper.Extensions.Microsoft.DependencyInjection is OBSOLETE — do NOT use it
- Class libraries need Microsoft.Extensions.DependencyInjection.Abstractions 8.0.0 for IServiceCollection
- Include ALL using statements in every file — never rely on transitive references
- Interface signatures MUST exactly match implementation signatures
- Do NOT call extension methods that don't exist
- Do NOT create recursive extension methods
"""

# -- Code reviewer -------------------------------------------------------------
REVIEW_SYSTEM = """
You are a .NET 8 code reviewer. Your job is to FIX build errors only.
Return the corrected complete file. No explanation. No markdown fences.

FIX THESE ISSUES ONLY:
1. Missing using statements — add ALL required usings for every type used in the file
2. Syntax errors — fix them
3. Missing interface implementations — add the missing methods
4. Type mismatches — correct the types
5. Missing constructors or DI parameters — add them
6. Guid id -> change to int id
7. NotImplementedException / TODO — replace with actual implementation
8. Empty catch blocks — add logging or rethrow
9. Interface-implementation signature mismatch — make them match exactly
10. Recursive extension methods — fix to call framework method instead
11. Calling extension methods that don't exist — remove or implement them
12. Missing middleware extension methods — add them or use app.UseMiddleware<T>()
13. CancellationToken without = default in controller methods — add = default
14. Controller using wrong model type (e.g. {Model} instead of Create{Model}/Update{Model}) — fix to use Create{Model} for POST, Update{Model} for PUT
15. Service calling non-existent methods like GetCountAsync() — repo returns (Items, TotalCount) tuple directly
16. Extension mapping properties that don't exist on target (e.g. CreatedAt on Create/Update models) — remove those mappings
17. Program.cs chaining incompatible return types (IMvcBuilder vs IServiceCollection) — make each call a separate statement
18. Validators missing using for model namespace — add using {Project}.Presentation.Models;
19. Service UpdateAsync setting properties that don't exist on entity (e.g. MiddleName, Email when entity only has Name, Address) — fix to match actual entity properties

CRITICAL USING DIRECTIVES (add if types are used):
- Microsoft.EntityFrameworkCore (for DbContext, DbSet, UseSqlServer)
- Microsoft.Extensions.DependencyInjection (for IServiceCollection)
- Microsoft.Extensions.Configuration (for IConfiguration)
- Microsoft.IdentityModel.Tokens (for TokenValidationParameters, SymmetricSecurityKey)
- System.Security.Claims (for ClaimsIdentity, ClaimsPrincipal)
- System.Threading.RateLimiting (for QueueProcessingOrder)
- Microsoft.AspNetCore.RateLimiting (for AddRateLimiter)
- Microsoft.AspNetCore.Mvc (for ProblemDetails, ControllerBase)
- System.Text (for Encoding)
- FluentValidation (for AbstractValidator)

DO NOT CHANGE:
- Class names (keep them exactly as they are)
- Method names (keep them exactly as they are)
- File structure or folder organization
- Property names
- The overall architecture pattern

If the file has no issues, return it unchanged.
If the file is clearly in the wrong project, return:
// SKIP: File in wrong location. Should be in [correct path]

Return ONLY the fixed file content.
"""


async def _review_and_fix(
    client: httpx.AsyncClient,
    files: dict[str, str],
    project_name: str,
    keys: list[str],
    model: str,
    q: Queue,
    step: int,
) -> dict[str, str]:
    fixed: dict[str, str] = {}
    cs_files    = {k: v for k, v in files.items() if k.endswith(".cs")}
    other_files = {k: v for k, v in files.items() if not k.endswith(".cs")}
    total = len(cs_files)
    skipped_files = []

    # Build a file list context so reviewer knows what exists
    file_list_context = "Other files in this project:\n" + "\n".join(f"- {p}" for p in cs_files.keys())

    for i, (path, code) in enumerate(cs_files.items()):
        await q.put(_sse("agent_message", {
            "agent": "SeniorReviewer",
            "preview": f"Reviewing {path} ({i + 1}/{total})...",
            "step": step,
        }))
        try:
            # Determine which layer this file belongs to for context
            if f"{project_name}.Data" in path:
                layer_context = get_data_layer_context(project_name)
            elif f"{project_name}.Business" in path:
                layer_context = get_business_layer_context(project_name)
            elif f"{project_name}.Presentation" in path:
                layer_context = get_presentation_layer_context(project_name)
            else:
                layer_context = ""

            result = await _llm(
                client,
                system=REVIEW_SYSTEM,
                user=f"""Architecture context:
{layer_context}

{file_list_context}

Build rules:
{DOTNET_PACKAGES}

File to review: {path}

{code}""",
                step_label="SeniorReviewer",
                keys=keys, model=model, q=q, step=step,
            )
            cleaned_result = _strip_fences(result)
            
            # Check if file was marked for skipping due to wrong location
            if cleaned_result.strip().startswith("// SKIP:"):
                logger.warning(f"Skipping file in wrong location: {path} - {cleaned_result}")
                skipped_files.append(path)
                continue
            
            # Safety: if reviewer returned something drastically shorter, keep original
            if len(cleaned_result) < len(code) * 0.3:
                logger.warning("Reviewer truncated %s (from %d to %d chars) — keeping original", path, len(code), len(cleaned_result))
                fixed[path] = code
            else:
                fixed[path] = cleaned_result
        except Exception as ex:
            logger.warning("Review failed for %s: %s — keeping original", path, ex)
            fixed[path] = code

    if skipped_files:
        await q.put(_sse("agent_message", {
            "agent": "SeniorReviewer",
            "preview": f"Removed {len(skipped_files)} files in wrong locations",
            "step": step,
        }))

    fixed.update(other_files)
    return fixed


# -- Static build validator (no .NET SDK needed) ------------------------------
def _validate_build(files: dict[str, str], project_name: str) -> list[str]:
    """Validate cross-file consistency without .NET SDK.
    Checks: missing references, namespace mismatches, interface implementations.
    Returns list of error messages (empty = all good).
    """
    errors: list[str] = []
    cs_files = {k: v for k, v in files.items() if k.endswith(".cs")}

    # Collect all defined classes/interfaces
    defined_types: set[str] = set()
    for path, code in cs_files.items():
        for match in re.finditer(r'(?:public|internal)\s+(?:static\s+)?(?:class|interface|record|struct)\s+(\w+)', code):
            defined_types.add(match.group(1))

    # Check each file for issues
    for path, code in cs_files.items():
        # 1. Check namespace matches folder
        ns_match = re.search(r'namespace\s+([\w.]+)', code)
        if ns_match:
            ns = ns_match.group(1)
            # Extract expected namespace from path
            path_parts = path.replace("/", ".").replace(".cs", "")
            # Remove filename from path to get folder namespace
            folder_ns = ".".join(path.replace("/", ".").split(".")[:-1])
            if not ns.startswith(project_name):
                errors.append(f"{path}: namespace '{ns}' doesn't start with '{project_name}'")

        # 2. Check for Guid id (should be int)
        if re.search(r'\bGuid\s+[Ii]d\b', code) and 'Guid' in code:
            if 'TokenService' not in path and 'Auth' not in path:
                errors.append(f"{path}: uses Guid for Id (should be int)")

        # 3. Check for empty classes
        class_match = re.search(r'(?:public|internal)\s+(?:static\s+)?class\s+\w+[^{{]*\{{\s*\}}', code)
        if class_match and 'Program' not in path:
            errors.append(f"{path}: contains empty class body")

        # 4. Check for NotImplementedException
        if 'NotImplementedException' in code:
            errors.append(f"{path}: contains NotImplementedException")

        # 5. Check interface implementations reference existing interfaces
        impl_match = re.search(r'class\s+\w+\s*:\s*([\w,\s<>]+)', code)
        if impl_match:
            bases = [b.strip().split('<')[0] for b in impl_match.group(1).split(',')]
            for base in bases:
                if base.startswith('I') and base[1:2].isupper() and base not in defined_types:
                    if base not in ('IEntityTypeConfiguration', 'IServiceCollection', 'IConfiguration',
                                    'ILogger', 'IHostEnvironment', 'IWebHostEnvironment',
                                    'IDisposable', 'IAsyncDisposable'):
                        errors.append(f"{path}: implements '{base}' but it's not defined in project")

        # 6. Check Program.cs has AddBusinessServices
        if 'Program.cs' in path:
            if 'AddBusinessServices' not in code:
                errors.append(f"{path}: missing AddBusinessServices() call")
            if 'MapControllers' not in code:
                errors.append(f"{path}: missing MapControllers() call")
            if 'AddControllers' not in code:
                errors.append(f"{path}: missing AddControllers() call")

        # 7. Check AppDbContext has DbSet properties
        if 'AppDbContext' in path:
            if 'DbSet<' not in code:
                errors.append(f"{path}: AppDbContext missing DbSet<> properties")

    # 8. Check required files exist
    required_patterns = [
        f"{project_name}.Data/AppDbContext.cs",
        f"{project_name}.Presentation/Program.cs",
    ]
    for pattern in required_patterns:
        if not any(pattern in f for f in files.keys()):
            errors.append(f"Missing required file: {pattern}")

    # 9. Check .sln exists
    if not any(f.endswith(".sln") for f in files.keys()):
        errors.append("Missing .sln file")

    return errors


# -- YAML cleanup helper -------------------------------------------------------
def _clean_yaml(text: str) -> str:
    """Remove markdown code fences and backticks from YAML input."""
    text = text.strip()
    # Remove opening fence with optional language specifier (```yaml, ```json, ```)
    text = re.sub(r'^```[a-zA-Z0-9]*\s*\n', '', text)
    # Remove closing fence
    text = re.sub(r'\n```\s*$', '', text)
    # Remove any remaining standalone fence lines
    text = re.sub(r'^\s*```[a-zA-Z0-9]*\s*$', '', text, flags=re.MULTILINE)
    return text.strip()


# -- Background job ------------------------------------------------------------
async def _run_codegen(job_id: str, openapi_yaml: str, project_name: str, llm_provider: str, include_tests: bool):
    q = _job_queues[job_id]
    total_steps = 13 if include_tests else 10

    async def status(agent: str, message: str, step: int):
        await q.put(_sse("status", {
            "agent": agent,
            "message": message,
            "step": step,
            "total": total_steps,
            "percent": int((step / total_steps) * 100),
        }))

    # Clean YAML input of markdown code fences
    openapi_yaml = _clean_yaml(openapi_yaml)
    all_files: dict[str, str] = {}
    _job_incremental_files[job_id] = {}  # Initialize incremental storage

    async def save_incremental(step_name: str):
        """Save current state and make it downloadable immediately."""
        _job_incremental_files[job_id] = dict(all_files)
        zip_bytes = _build_zip(all_files, f"{project_name}_Step{step_name}")
        zip_b64 = base64.b64encode(zip_bytes).decode()
        if job_id not in _job_artifacts:
            _job_artifacts[job_id] = {"project_name": project_name}
        _job_artifacts[job_id][f"step_{step_name}"] = zip_b64
        await q.put(_sse("incremental_ready", {
            "step": step_name,
            "file_count": len(all_files),
            "download_url": f"/api/codegen/download/{job_id}/step-{step_name}",
        }))

    try:
        keys  = settings.groq_api_keys
        model = settings.groq_model
        if not keys:
            raise ValueError("No GROQ_API_KEY configured in .env. Please add GROQ_API_KEY=your_key_here to your .env file.")

        await status("System", f"Starting code generation for {project_name}...", 0)

        async with httpx.AsyncClient(timeout=60.0) as client:

            # Step 1: Architect plan
            await status("Architect", f"Step 1/{total_steps} — Analysing OpenAPI spec...", 1)
            plan_raw = await _llm(
                client,
                system=f"""You are a principal .NET 8 solution architect.
Analyse the OpenAPI spec and output ONLY valid JSON for a 4-project clean architecture solution:
{{
  "solution": "{project_name}",
  "projects": [
    "{project_name}.Data",
    "{project_name}.Business",
    "{project_name}.Presentation",
    "{project_name}.Tests"
  ],
  "controllers": ["<Name>"],
  "entities": ["<Name>"],
  "services": ["<Name>"]
}}
No explanation. JSON only.""",
                user=f"OpenAPI spec:\n{openapi_yaml[:4000]}",
                step_label="Architect", keys=keys, model=model, q=q, step=1,
            )
            try:
                plan = json.loads(re.search(r'\{.*\}', plan_raw, re.DOTALL).group())
            except Exception:
                plan = {"controllers": ["Resource"], "entities": ["Resource"], "services": ["Resource"], "protectedEndpoints": [], "publicEndpoints": []}

            controllers = plan.get("controllers", ["Resource"])
            entities    = plan.get("entities", ["Resource"])
            
            # CRITICAL FIX: Ensure controllers and entities match 1:1 to avoid orphaned controllers
            # If controller count doesn't match entity count, align them
            if len(controllers) != len(entities):
                logger.warning(f"Controller count ({len(controllers)}) != Entity count ({len(entities)}). Aligning...")
                min_count = min(len(controllers), len(entities))
                controllers = controllers[:min_count]
                entities = entities[:min_count]
            
            await status("Architect", f"Plan: {len(controllers)} controller(s), {len(entities)} entity(ies)", 1)

            # Architect generates solution structure deterministically (no LLM needed)
            all_files[f"{project_name}.sln"] = _generate_sln(project_name, include_tests)
            all_files[f"{project_name}.Data/{project_name}.Data.csproj"] = _generate_data_csproj(project_name)
            all_files[f"{project_name}.Business/{project_name}.Business.csproj"] = _generate_business_csproj(project_name)
            all_files[f"{project_name}.Presentation/{project_name}.Presentation.csproj"] = _generate_presentation_csproj(project_name)
            all_files[f"{project_name}.Presentation/Properties/launchSettings.json"] = _generate_launch_settings(project_name)
            if include_tests:
                all_files[f"{project_name}.Tests/{project_name}.Tests.csproj"] = _generate_tests_csproj(project_name)
            await status("Architect", f"Solution structure created ({len(all_files)} files)", 1)
            await save_incremental("1_architect")

            # Step 2: Config files (appsettings, README)
            await status("Coder", f"Step 2/{total_steps} — Generating config files...", 2)

            proj_text = await _llm(
                client,
                system="""You are a senior .NET 8 developer.
Generate COMPLETE files using EXACTLY this format:
=== FILE: <path> ===
<complete code>
=== END FILE ===
No explanation outside file blocks.""",
                user=f"""{DOTNET_PACKAGES}
{get_solution_structure_context(project_name)}
{get_naming_rules()}
Generate configuration files for '{project_name}':

1. {project_name}.Presentation/appsettings.json — include sections:
   ConnectionStrings.DefaultConnection (SQL Server placeholder)
   JwtSettings: Secret, Issuer, Audience, ExpiryMinutes
   Serilog: MinimumLevel, WriteTo (Console + File)
   AllowedHosts: "*"

2. {project_name}.Presentation/appsettings.Development.json — dev overrides:
   ConnectionStrings.DefaultConnection using InMemory
   Serilog MinimumLevel: Debug

3. README.md — solution structure, setup instructions, how to run
   Mention: dotnet restore, dotnet build, dotnet run --project {project_name}.Presentation
   List all projects and their purpose""",
                step_label="Coder", keys=keys, model=model, q=q, step=2,
            )
            extracted_proj_files = _extract_files(proj_text)
            all_files.update(extracted_proj_files)
            await status("Coder", f"Config files done ({len(all_files)} files so far)", 2)
            await save_incremental("2_solution")

            # Step 3: Auth & Security (Presentation project)
            await status("SecurityExpert", f"Step 3/{total_steps} — Generating JWT auth, middleware (Presentation)...", 3)
            # Step 3 LLM call skipped - using deterministic stubs
            # TODO: Re-enable LLM auth generation when token budget allows
            _pn = project_name
            all_files[f"{_pn}.Presentation/Authorization/JwtSettings.cs"] = "namespace " + _pn + ".Presentation.Authorization;\n\npublic class JwtSettings\n{\n    public string Secret { get; set; } = \"your-secret-key-that-is-at-least-32-chars!\";\n    public string Issuer { get; set; } = \"" + _pn + "\";\n    public string Audience { get; set; } = \"" + _pn + "\";\n    public int ExpiryMinutes { get; set; } = 60;\n}"
            all_files[f"{_pn}.Presentation/Authorization/ITokenService.cs"] = "namespace " + _pn + ".Presentation.Authorization;\n\npublic interface ITokenService { string GenerateToken(string userId, string role); }"
            all_files[f"{_pn}.Presentation/Authorization/JwtTokenService.cs"] = "using System.IdentityModel.Tokens.Jwt;\nusing System.Security.Claims;\nusing System.Text;\nusing Microsoft.IdentityModel.Tokens;\n\nnamespace " + _pn + ".Presentation.Authorization;\n\npublic class JwtTokenService : ITokenService\n{\n    private readonly JwtSettings _s;\n    public JwtTokenService(JwtSettings s) { _s = s; }\n    public string GenerateToken(string userId, string role)\n    {\n        var key = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(_s.Secret));\n        var creds = new SigningCredentials(key, SecurityAlgorithms.HmacSha256);\n        var token = new JwtSecurityToken(_s.Issuer, _s.Audience, new[] { new Claim(ClaimTypes.NameIdentifier, userId), new Claim(ClaimTypes.Role, role) }, expires: DateTime.UtcNow.AddMinutes(_s.ExpiryMinutes), signingCredentials: creds);\n        return new JwtSecurityTokenHandler().WriteToken(token);\n    }\n}"
            all_files[f"{_pn}.Presentation/Middleware/ExceptionHandlingMiddleware.cs"] = "using System.Net;\nusing Microsoft.AspNetCore.Mvc;\n\nnamespace " + _pn + ".Presentation.Middleware;\n\npublic class ExceptionHandlingMiddleware\n{\n    private readonly RequestDelegate _next; private readonly ILogger<ExceptionHandlingMiddleware> _log;\n    public ExceptionHandlingMiddleware(RequestDelegate next, ILogger<ExceptionHandlingMiddleware> log) { _next = next; _log = log; }\n    public async Task InvokeAsync(HttpContext ctx) { try { await _next(ctx); } catch (KeyNotFoundException ex) { _log.LogWarning(ex, \"Not found\"); ctx.Response.StatusCode = 404; await ctx.Response.WriteAsJsonAsync(new ProblemDetails { Title = \"Not Found\", Status = 404, Detail = ex.Message }); } catch (Exception ex) { _log.LogError(ex, \"Error\"); ctx.Response.StatusCode = 500; await ctx.Response.WriteAsJsonAsync(new ProblemDetails { Title = \"Error\", Status = 500 }); } }\n}"
            all_files[f"{_pn}.Presentation/Middleware/RequestLoggingMiddleware.cs"] = "using System.Diagnostics;\n\nnamespace " + _pn + ".Presentation.Middleware;\n\npublic class RequestLoggingMiddleware\n{\n    private readonly RequestDelegate _next; private readonly ILogger<RequestLoggingMiddleware> _log;\n    public RequestLoggingMiddleware(RequestDelegate next, ILogger<RequestLoggingMiddleware> log) { _next = next; _log = log; }\n    public async Task InvokeAsync(HttpContext ctx) { var sw = Stopwatch.StartNew(); await _next(ctx); _log.LogInformation(\"{M} {P} {S} in {E}ms\", ctx.Request.Method, ctx.Request.Path, ctx.Response.StatusCode, sw.ElapsedMilliseconds); }\n}"
            all_files[f"{_pn}.Presentation/Middleware/MiddlewareExtensions.cs"] = "namespace " + _pn + ".Presentation.Middleware;\n\npublic static class MiddlewareExtensions\n{\n    public static IApplicationBuilder UseExceptionHandling(this IApplicationBuilder app) => app.UseMiddleware<ExceptionHandlingMiddleware>();\n    public static IApplicationBuilder UseRequestLogging(this IApplicationBuilder app) => app.UseMiddleware<RequestLoggingMiddleware>();\n}"
            await status("SecurityExpert", f"Auth files done ({len(all_files)} files so far)", 3)
            await save_incremental("3_auth")

            # Step 4: Models + Extensions + Validators per entity
            await status("Coder", f"Step 4/{total_steps} - Generating models, extensions, validators...", 4)
            for entity in entities[:3]:
                # 4a: Data model FIRST - then pass to other layers for consistency
                data_model_text = await _llm(
                    client,
                    system="""You are a senior .NET 8 developer.
Generate COMPLETE C# files using EXACTLY this format:
=== FILE: <path> ===
<complete code>
=== END FILE ===
Full implementations. No TODOs. Initialize all string properties = string.Empty.""",
                    user=f"""{get_data_layer_context(project_name)}

Generate Data model for '{entity}' in '{project_name}.Data':

File 1: {project_name}.Data/Models/{entity}.cs
- namespace {project_name}.Data.Models
- public class {entity}
- Properties: Id (int), CreatedAt (DateTime), UpdatedAt (DateTime) + ALL business fields from OpenAPI
- Initialize strings = string.Empty. Use proper C# types.

File 2: {project_name}.Data/Configurations/{entity}Configuration.cs
- namespace {project_name}.Data.Configurations
- using {project_name}.Data.Models;
- using Microsoft.EntityFrameworkCore;
- using Microsoft.EntityFrameworkCore.Metadata.Builders;
- IEntityTypeConfiguration<{entity}>
- HasKey(x => x.Id), Property(x => x.Id).ValueGeneratedOnAdd()

OpenAPI spec:
{openapi_yaml[:1500]}""",
                    step_label="Coder", keys=keys, model=model, q=q, step=4,
                )
                all_files.update(_extract_files(data_model_text))

                # Extract Data model to pass to other layers for property consistency
                data_model_key = f"{project_name}.Data/Models/{entity}.cs"
                data_model_content = all_files.get(data_model_key, "// Data model not generated")

                # 4b: Business models + extensions - MUST match Data model properties
                biz_model_text = await _llm(
                    client,
                    system="""You are a senior .NET 8 developer.
Generate COMPLETE C# files using EXACTLY this format:
=== FILE: <path> ===
<complete code>
=== END FILE ===
Full implementations. Map ALL properties explicitly. No placeholder comments. Initialize strings = string.Empty.""",
                    user=f"""{get_business_layer_context(project_name)}

REFERENCE - Data model (Business MUST have same properties):
{data_model_content}

Generate Business layer for '{entity}' in '{project_name}.Business':

File 1: {project_name}.Business/Models/{entity}.cs - COPY all properties from Data model above
File 2: {project_name}.Business/Models/Create{entity}.cs - all props EXCEPT Id, CreatedAt, UpdatedAt
File 3: {project_name}.Business/Models/Update{entity}.cs - same as Create. MUST generate.
File 4: {project_name}.Business/Models/Paged{entity}.cs - List<{entity}> Items, int TotalCount, Page, PageSize
File 5: {project_name}.Business/Extensions/{entity}Extensions.cs
  - using {project_name}.Data.Models; using {project_name}.Business.Models;
  - ToBusinessModel(this Data.Models.{entity}) returns Business.Models.{entity} - map ALL props
  - ToDataModel(this Business.Models.Create{entity}) returns Data.Models.{entity} - map ALL props, set CreatedAt=UtcNow
  - ToBusinessModels(this IEnumerable<Data.Models.{entity}>) returns List<Business.Models.{entity}>
  - ToPagedResult(...) returns Business.Models.Paged{entity}

Generate ALL 5 files.""",
                    step_label="Coder", keys=keys, model=model, q=q, step=4,
                )
                all_files.update(_extract_files(biz_model_text))

                # 4c: Presentation models + extensions + validators - MUST match Data model properties
                # Also pass the Business Create/Update models to ensure Presentation matches exactly
                biz_create_key = f"{project_name}.Business/Models/Create{entity}.cs"
                biz_update_key = f"{project_name}.Business/Models/Update{entity}.cs"
                biz_create_content = all_files.get(biz_create_key, "// not generated")
                biz_update_content = all_files.get(biz_update_key, "// not generated")

                pres_model_text = await _llm(
                    client,
                    system="""You are a senior .NET 8 developer.
Generate COMPLETE C# files using EXACTLY this format:
=== FILE: <path> ===
<complete code>
=== END FILE ===
Full implementations. Map ALL properties explicitly. No placeholder comments. Initialize strings = string.Empty.""",
                    user=f"""{get_presentation_layer_context(project_name)}

REFERENCE - Data model (Presentation read model MUST have same properties):
{data_model_content}

REFERENCE - Business Create model (Presentation Create MUST have IDENTICAL properties):
{biz_create_content}

REFERENCE - Business Update model (Presentation Update MUST have IDENTICAL properties):
{biz_update_content}

Generate Presentation layer for '{entity}' in '{project_name}.Presentation':

File 1: {project_name}.Presentation/Models/{entity}.cs - COPY all properties from Data model (Id, all fields, CreatedAt, UpdatedAt)
File 2: {project_name}.Presentation/Models/Create{entity}.cs - MUST have EXACTLY same properties as Business Create model above. NO Id, NO CreatedAt, NO UpdatedAt.
File 3: {project_name}.Presentation/Models/Update{entity}.cs - MUST have EXACTLY same properties as Business Update model above. NO Id, NO CreatedAt, NO UpdatedAt.
File 4: {project_name}.Presentation/Models/Paged{entity}.cs - List<{entity}> Items, int TotalCount, Page, PageSize
File 5: {project_name}.Presentation/Extensions/{entity}Extensions.cs
  - using {project_name}.Business.Models; using {project_name}.Presentation.Models;
  - ToBusinessModel(this Presentation.Models.Create{entity} m) returns Business.Models.Create{entity} — map ONLY properties that exist on Business Create model
  - ToBusinessModel(this Presentation.Models.Update{entity} m) returns Business.Models.Update{entity} — map ONLY properties that exist on Business Update model
  - ToApiModel(this Business.Models.{entity} m) returns Presentation.Models.{entity} — map ALL properties including Id, CreatedAt, UpdatedAt
  - ToPagedApiModel(this Business.Models.Paged{entity} m) returns Presentation.Models.Paged{entity}
  - CRITICAL: Do NOT map CreatedAt/UpdatedAt in ToBusinessModel for Create/Update — those properties do NOT exist on Create/Update models
File 6: {project_name}.Presentation/Validators/Create{entity}Validator.cs
  - using FluentValidation;
  - using {project_name}.Presentation.Models;
  - namespace {project_name}.Presentation.Validators;
  - public class Create{entity}Validator : AbstractValidator<Create{entity}>
File 7: {project_name}.Presentation/Validators/Update{entity}Validator.cs
  - using FluentValidation;
  - using {project_name}.Presentation.Models;
  - namespace {project_name}.Presentation.Validators;
  - public class Update{entity}Validator : AbstractValidator<Update{entity}>

Generate ALL 7 files.""",
                    step_label="Coder", keys=keys, model=model, q=q, step=4,
                )
                all_files.update(_extract_files(pres_model_text))

            await status("Coder", f"Models + Extensions done ({len(all_files)} files so far)", 4)
            await save_incremental("4_models")

            # Step 5: DbContext + Repositories (Data project)
            await status("Coder", f"Step 5/{total_steps} — Generating DbContext and repositories (Data project)...", 5)
            
            config_prompts = []
            for idx, entity in enumerate(entities[:3], 1):
                config_prompts.append(
                    f"{idx+1}. {project_name}.Data/Configurations/{entity}Configuration.cs"
                )
            config_list = ", ".join(entities[:3])
            
            # 5a: AppDbContext
            db_text = await _llm(
                client,
                system="""You are a senior .NET 8 developer.
Generate COMPLETE C# files using EXACTLY this format:
=== FILE: <path> ===
<complete code>
=== END FILE ===
Full implementations. No TODOs.""",
                user=f"""{get_data_layer_context(project_name)}

Generate AppDbContext for '{project_name}.Data':

File 1: {project_name}.Data/AppDbContext.cs
- namespace {project_name}.Data
- using {project_name}.Data.Models;
- using Microsoft.EntityFrameworkCore;
- DbSet<> properties for ALL entities: {config_list}
- OnModelCreating: apply all configurations
- SaveChangesAsync override: set CreatedAt on insert, UpdatedAt on update
- Use {project_name}.Data.Models namespace for entities
- DO NOT use BaseEntity or any base class. Each entity has its own Id, CreatedAt, UpdatedAt properties.

Full implementation. Include all required usings.""",
                step_label="Coder", keys=keys, model=model, q=q, step=5,
            )
            all_files.update(_extract_files(db_text))

            # 5b: IBaseRepository + BaseRepository
            base_repo_text = await _llm(
                client,
                system="""You are a senior .NET 8 developer.
Generate COMPLETE C# files using EXACTLY this format:
=== FILE: <path> ===
<complete code>
=== END FILE ===
Full implementations. No TODOs.""",
                user=f"""{get_data_layer_context(project_name)}

Generate base repository infrastructure:

File 1: {project_name}.Data/Contracts/IBaseRepository.cs
- namespace {project_name}.Data.Contracts
- public interface IBaseRepository<T> where T : class
- Methods: GetByIdAsync(int id, CancellationToken), GetAllAsync(int page, int pageSize, CancellationToken), CreateAsync(T entity, CancellationToken), UpdateAsync(T entity, CancellationToken), DeleteAsync(int id, CancellationToken), ExistsAsync(int id, CancellationToken)
- All return Task<T?>, Task<(IEnumerable<T>, int)>, Task<T>, Task<bool> as appropriate

File 2: {project_name}.Data/Repositories/BaseRepository.cs
- namespace {project_name}.Data.Repositories
- using {project_name}.Data.Contracts;
- using Microsoft.EntityFrameworkCore;
- public class BaseRepository<T> : IBaseRepository<T> where T : class
- protected readonly AppDbContext _context; protected readonly DbSet<T> _dbSet;
- Constructor sets _context and _dbSet = context.Set<T>()
- Full CRUD: FindAsync, Skip/Take, Add, Remove, SaveChangesAsync

Both files must compile independently. Include ALL usings.""",
                step_label="Coder", keys=keys, model=model, q=q, step=5,
            )
            all_files.update(_extract_files(base_repo_text))

            # 5c: Per-entity repositories
            for entity in entities[:3]:
                repo_text = await _llm(
                    client,
                    system="""You are a senior .NET 8 developer.
Generate COMPLETE C# files using EXACTLY this format:
=== FILE: <path> ===
<complete code>
=== END FILE ===
Full implementations. No TODOs.""",
                    user=f"""{get_data_layer_context(project_name)}

Generate repository for '{entity}':

File 1: {project_name}.Data/Contracts/I{entity}Repository.cs
- namespace {project_name}.Data.Contracts
- using {project_name}.Data.Models;
- public interface I{entity}Repository : IBaseRepository<{entity}> {{ }}

File 2: {project_name}.Data/Repositories/{entity}Repository.cs
- namespace {project_name}.Data.Repositories
- using {project_name}.Data.Models;
- using {project_name}.Data.Contracts;
- public class {entity}Repository : BaseRepository<{entity}>, I{entity}Repository
- Constructor: public {entity}Repository(AppDbContext context) : base(context) {{ }}

Use int id. Include all usings.""",
                    step_label="Coder", keys=keys, model=model, q=q, step=5,
                )
                all_files.update(_extract_files(repo_text))

            # 5d: DataModule (CompositionModule)
            data_module_text = await _llm(
                client,
                system="""You are a senior .NET 8 developer.
Generate COMPLETE C# files using EXACTLY this format:
=== FILE: <path> ===
<complete code>
=== END FILE ===
Full implementations. No TODOs.""",
                user=f"""{get_data_layer_context(project_name)}

Generate DI registration:

File 1: {project_name}.Data/CompositionModule/DataModule.cs
- namespace {project_name}.Data.CompositionModule
- static class DataModule
- Extension method: AddDataServices(this IServiceCollection services, IConfiguration config)
- Register: AppDbContext with UseSqlServer
- Register: I{entities[0]}Repository -> {entities[0]}Repository (and all others: {config_list})
- DO NOT register IBaseRepository<> as open generic - only register concrete repos
- Return services

Include usings: Microsoft.EntityFrameworkCore, Microsoft.Extensions.DependencyInjection, Microsoft.Extensions.Configuration""",
                step_label="Coder", keys=keys, model=model, q=q, step=5,
            )
            all_files.update(_extract_files(data_module_text))
            await status("Coder", f"Data project done ({len(all_files)} files so far)", 5)
            await save_incremental("5_data_layer")

            # Step 6: Business services
            await status("Coder", f"Step 6/{total_steps} — Generating business services (Business project)...", 6)
            for entity in entities[:3]:
                # Pass the Data model and Business Update model so LLM knows exact properties
                data_model_key = f"{project_name}.Data/Models/{entity}.cs"
                data_model_content = all_files.get(data_model_key, "// not generated")
                biz_update_key = f"{project_name}.Business/Models/Update{entity}.cs"
                biz_update_content = all_files.get(biz_update_key, "// not generated")

                svc_text = await _llm(
                    client,
                    system="""You are a senior .NET 8 developer.
Generate COMPLETE C# files using EXACTLY this format:
=== FILE: <path> ===
<complete code>
=== END FILE ===
Full implementations. No TODOs.""",
                    user=f"""{get_business_layer_context(project_name)}

REFERENCE - Data entity (these are the ONLY properties that exist):
{data_model_content}

REFERENCE - Update model (use ONLY these properties in UpdateAsync):
{biz_update_content}

Generate service files for '{entity}' in '{project_name}.Business':

File 1: {project_name}.Business/Contracts/I{entity}Service.cs
- namespace {project_name}.Business.Contracts
- using {project_name}.Business.Models;
- public interface I{entity}Service
- Methods: GetAllAsync(int page, int pageSize, CancellationToken ct = default), GetByIdAsync(int id, CancellationToken ct = default), CreateAsync(Create{entity} model, CancellationToken ct = default), UpdateAsync(int id, Update{entity} model, CancellationToken ct = default), DeleteAsync(int id, CancellationToken ct = default)
- Returns: Task<Paged{entity}>, Task<{entity}>, Task<{entity}>, Task<{entity}>, Task

File 2: {project_name}.Business/Services/{entity}Service.cs
- namespace {project_name}.Business.Services
- using {project_name}.Data.Contracts;
- using {project_name}.Business.Models;
- using {project_name}.Business.Contracts;
- using {project_name}.Business.Extensions;
- public class {entity}Service : I{entity}Service
- Constructor: I{entity}Repository repository, ILogger<{entity}Service> logger
- GetAllAsync: var result = await _repository.GetAllAsync(page, pageSize, ct); return result.ToPagedResult(page, pageSize); — repo returns (IEnumerable<T> Items, int TotalCount) tuple directly, do NOT call .GetCountAsync()
- CreateAsync: var entity = model.ToDataModel(); var created = await _repository.CreateAsync(entity, ct); return created.ToBusinessModel();
- UpdateAsync: fetch entity via GetByIdAsync, then set ONLY the properties from Update model above (match property names exactly), set entity.UpdatedAt = DateTime.UtcNow, then await _repository.UpdateAsync(entity, ct) and return .ToBusinessModel()
- DeleteAsync: if (!await _repository.ExistsAsync(id, ct)) throw KeyNotFoundException; await _repository.DeleteAsync(id, ct);
- Throw KeyNotFoundException when entity not found

CRITICAL: The repository GetAllAsync returns a TUPLE (IEnumerable<T> Items, int TotalCount). Do NOT call any GetCountAsync() method — it does not exist.

Generate BOTH files. Include ALL usings.""",
                    step_label="Coder", keys=keys, model=model, q=q, step=6,
                )
                all_files.update(_extract_files(svc_text))

            # BusinessModule
            business_module_text = await _llm(
                client,
                system="""You are a senior .NET 8 developer.
Generate COMPLETE C# files using EXACTLY this format:
=== FILE: <path> ===
<complete code>
=== END FILE ===
Full implementations. No TODOs.""",
                user=f"""{get_business_layer_context(project_name)}

File 1: {project_name}.Business/CompositionModule/BusinessModule.cs
- namespace {project_name}.Business.CompositionModule
- static class BusinessModule
- Extension method: AddBusinessServices(this IServiceCollection services, IConfiguration config)
- FIRST call: services.AddDataServices(config)  // from {project_name}.Data.CompositionModule
- THEN register each service: {', '.join(f'services.AddScoped<I{e}Service, {e}Service>()' for e in entities[:3])}
- Return services

Include usings: Microsoft.Extensions.DependencyInjection, Microsoft.Extensions.Configuration, {project_name}.Data.CompositionModule, {project_name}.Business.Contracts, {project_name}.Business.Services""",
                step_label="Coder", keys=keys, model=model, q=q, step=6,
            )
            all_files.update(_extract_files(business_module_text))
            await status("Coder", f"Business services done ({len(all_files)} files so far)", 6)
            await save_incremental("6_business_layer")

            # Step 7: Controllers (Presentation project)
            await status("Coder", f"Step 7/{total_steps} — Generating controllers (Presentation project)...", 7)
            # CRITICAL FIX: Ensure we only generate controllers that have corresponding entities
            # This prevents orphaned controllers like LicenseController without License entity
            valid_controller_entity_pairs = list(zip(controllers[:3], entities[:3]))
            if len(valid_controller_entity_pairs) == 0:
                logger.warning("No valid controller-entity pairs found. Using default Resource.")
                valid_controller_entity_pairs = [("Resource", "Resource")]
            
            for ctrl, entity in valid_controller_entity_pairs:
                # Pass the Presentation Create/Update models so LLM uses correct types
                pres_create_key = f"{project_name}.Presentation/Models/Create{entity}.cs"
                pres_update_key = f"{project_name}.Presentation/Models/Update{entity}.cs"
                pres_create_content = all_files.get(pres_create_key, "// not generated")
                pres_update_content = all_files.get(pres_update_key, "// not generated")

                ctrl_text = await _llm(
                    client,
                    system="""You are a senior .NET 8 Web API developer.
Generate COMPLETE C# files using EXACTLY this format:
=== FILE: <path> ===
<complete code>
=== END FILE ===
Production-ready. No TODOs.""",
                    user=f"""{get_presentation_layer_context(project_name)}

REFERENCE - These are the EXACT model types to use in the controller:
Create model (use in [HttpPost] [FromBody] parameter):
{pres_create_content}

Update model (use in [HttpPut] [FromBody] parameter):
{pres_update_content}

Generate controller for '{entity}' in '{project_name}.Presentation':
{project_name}.Presentation/Controllers/{ctrl}Controller.cs

RULES:
- using {project_name}.Presentation.Models;
- using {project_name}.Presentation.Extensions;
- using {project_name}.Business.Contracts;
- [ApiController] [Route("api/[controller]")]
- Constructor: I{entity}Service service, ILogger<{ctrl}Controller> logger
- [HttpGet] GetAllAsync([FromQuery] int page = 1, [FromQuery] int pageSize = 10, CancellationToken ct = default)
- [HttpGet("{{id}}")] GetByIdAsync(int id, CancellationToken ct = default)
- [HttpPost] CreateAsync([FromBody] Create{entity} model, CancellationToken ct = default) — use Create{entity} NOT {entity}
- [HttpPut("{{id}}")] UpdateAsync(int id, [FromBody] Update{entity} model, CancellationToken ct = default) — use Update{entity} NOT {entity}
- [HttpDelete("{{id}}")] DeleteAsync(int id, CancellationToken ct = default)
- Use .ToBusinessModel() for Create/Update input, .ToApiModel() for single output, .ToPagedApiModel() for paged output
- CancellationToken MUST have = default since it comes after optional params
- NO [Authorize] attributes
- Return Ok(), CreatedAtAction(), NoContent() as appropriate""",
                    step_label="Coder", keys=keys, model=model, q=q, step=7,
                )
                all_files.update(_extract_files(ctrl_text))
            await status("Coder", f"Controllers done ({len(all_files)} files so far)", 7)
            await save_incremental("7_controllers")

            # Step 8: Program.cs (Presentation project)
            await status("Coder", f"Step 8/{total_steps} — Generating Program.cs (Presentation project)...", 8)
            # Get the first entity's validator class name for AddValidatorsFromAssemblyContaining
            first_entity = entities[0] if entities else "Resource"
            prog_text = await _llm(
                client,
                system="""You are a senior .NET 8 developer.
Generate COMPLETE C# files using EXACTLY this format:
=== FILE: <path> ===
<complete code>
=== END FILE ===
Full production-ready Program.cs. No TODOs.""",
                user=f"""{DOTNET_PACKAGES}
{get_presentation_layer_context(project_name)}

CRITICAL BUILD RULES:
- Include ALL using statements
- Do NOT call extension methods that don't exist
- Do NOT create recursive extension methods
- builder.Host.UseSerilog() for Serilog integration
- EVERY method call on builder.Services returns IServiceCollection — do NOT chain with IMvcBuilder methods
- AddControllers() returns IMvcBuilder. Do NOT chain AddEndpointsApiExplorer() after it. Call separately on builder.Services.
- app.UseSwagger(), app.UseSwaggerUI(), app.MapControllers(), app.MapHealthChecks() are all called on app (WebApplication), NOT chained from IApplicationBuilder

Generate {project_name}.Presentation/Program.cs:

EXACT PATTERN TO FOLLOW (do not deviate):
```
using Serilog;
using FluentValidation;
using FluentValidation.AspNetCore;
using {project_name}.Business.CompositionModule;
using {project_name}.Presentation.Middleware;
using {project_name}.Presentation.Validators;

var builder = WebApplication.CreateBuilder(args);

builder.Host.UseSerilog((ctx, cfg) => cfg.ReadFrom.Configuration(ctx.Configuration));

builder.Services.AddBusinessServices(builder.Configuration);
builder.Services.AddControllers();
builder.Services.AddFluentValidationAutoValidation();
builder.Services.AddValidatorsFromAssemblyContaining<Create{first_entity}Validator>();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();
builder.Services.AddHealthChecks();

var app = builder.Build();

app.UseExceptionHandling();
app.UseRequestLogging();
app.UseHttpsRedirection();
app.UseSwagger();
app.UseSwaggerUI();
app.MapControllers();
app.MapHealthChecks("/health");

app.Run();
```

IMPORTANT:
- UseExceptionHandling and UseRequestLogging are defined in {project_name}.Presentation.Middleware.MiddlewareExtensions
- Each builder.Services.XYZ() call is a SEPARATE statement — never chain them
- Each app.XYZ() call is a SEPARATE statement — never chain them
- Do NOT add authentication/authorization code
- Do NOT reference ITokenService or JwtSettings

Generate ONLY the Program.cs file.""",
                step_label="Coder", keys=keys, model=model, q=q, step=8,
            )
            all_files.update(_extract_files(prog_text))
            await status("Coder", f"Program.cs done ({len(all_files)} files so far)", 8)
            await save_incremental("8_program")

            if include_tests:
                # Step 9: Unit Tests
                await status("TestEngineer", f"Step 9/{total_steps} — Generating unit tests...", 9)
                for entity in entities[:2]:
                    unit_text = await _llm(
                        client,
                        system="""You are a senior .NET test engineer.
Generate COMPLETE xUnit test files using EXACTLY this format:
=== FILE: <path> ===
<complete code>
=== END FILE ===
Full test implementations. No TODOs. Use Moq.""",
                        user=f"""Generate {project_name}.Tests/Unit/Services/{entity}ServiceTests.cs:
namespace {project_name}.Tests.Unit.Services
Mock: I{entity}Repository, ILogger<{entity}Service>
Tests (Arrange/Act/Assert):
- GetAllAsync_ReturnsPagedDto_WhenEntitiesExist
- GetAllAsync_ReturnsEmptyPaged_WhenNoEntities
- GetByIdAsync_ReturnsDto_WhenFound
- GetByIdAsync_ThrowsKeyNotFoundException_WhenNotFound
- CreateAsync_ReturnsDto_WhenValid
- UpdateAsync_ReturnsUpdatedDto_WhenFound
- UpdateAsync_ThrowsKeyNotFoundException_WhenNotFound
- DeleteAsync_Succeeds_WhenFound
- DeleteAsync_ThrowsKeyNotFoundException_WhenNotFound
Use [Theory]/[InlineData] where applicable.""",
                        step_label="TestEngineer", keys=keys, model=model, q=q, step=9,
                    )
                    all_files.update(_extract_files(unit_text))
                await status("TestEngineer", f"Unit tests done ({len(all_files)} files so far)", 9)
                await save_incremental("9_unit_tests")

                # Step 10: Integration Tests
                await status("TestEngineer", f"Step 10/{total_steps} — Generating integration tests...", 10)
                integ_text = await _llm(
                    client,
                    system="""You are a senior .NET test engineer.
Generate COMPLETE integration test files using EXACTLY this format:
=== FILE: <path> ===
<complete code>
=== END FILE ===
Full implementations using WebApplicationFactory. No TODOs.""",
                    user=f"""Generate integration test files for '{project_name}':
1. {project_name}.Tests/Integration/CustomWebApplicationFactory.cs
   WebApplicationFactory<Program>, replace SqlServer with InMemory, seed {entities[0]} test data
2. {project_name}.Tests/Integration/AuthHelper.cs
   GenerateJwtToken(string role), AdminToken/UserToken/ReadOnlyToken constants
3. {project_name}.Tests/Helpers/TestDataFactory.cs
   Create{entities[0]}Entity(), Create{entities[0]}Dto(), CreateCreate{entities[0]}Dto() with realistic data
4. {project_name}.Tests/Integration/{controllers[0]}ControllerIntegrationTests.cs
   GET(200), GET/id(200,404), POST(201 with token, 401 without), PUT(200 user, 403 readonly), DELETE(204 admin, 403 user)""",
                    step_label="TestEngineer", keys=keys, model=model, q=q, step=10,
                )
                all_files.update(_extract_files(integ_text))
                await status("TestEngineer", f"Integration tests done ({len(all_files)} files so far)", 10)
                await save_incremental("10_integration_tests")

                review_file_step = 11
            else:
                review_file_step = 9

            # Store pre-review snapshot (already saved incrementally, but keep for compatibility)
            pre_review_files = dict(all_files)
            pre_review_zip = _build_zip(pre_review_files, f"{project_name}_PreReview")
            pre_review_b64 = base64.b64encode(pre_review_zip).decode()
            if job_id not in _job_artifacts:
                _job_artifacts[job_id] = {"project_name": project_name}
            _job_artifacts[job_id]["pre_review_zip"] = pre_review_b64

            # Review source files
            await status("SeniorReviewer", f"Step {review_file_step}/{total_steps} — Reviewing source files for build errors, deprecated APIs, naming standards...", review_file_step)
            src_to_review = {k: v for k, v in all_files.items() if not k.startswith(f"{project_name}.Tests")}
            reviewed_src  = await _review_and_fix(client, src_to_review, project_name, keys, model, q, review_file_step)
            all_files.update(reviewed_src)
            await status("SeniorReviewer", f"Source review done ({len(reviewed_src)} files fixed)", review_file_step)
            await save_incremental(f"{review_file_step}_reviewed_source")

            if include_tests:
                test_review_step = review_file_step + 1
                await status("SeniorReviewer", f"Step {test_review_step}/{total_steps} — Reviewing test files...", test_review_step)
                test_to_review = {k: v for k, v in all_files.items() if k.startswith(f"{project_name}.Tests") and k.endswith(".cs")}
                reviewed_tests = await _review_and_fix(client, test_to_review, project_name, keys, model, q, test_review_step)
                all_files.update(reviewed_tests)
                await status("SeniorReviewer", f"Test review done ({len(reviewed_tests)} files fixed)", test_review_step)
                await save_incremental(f"{test_review_step}_reviewed_tests")
                package_step = test_review_step + 1
            else:
                package_step = review_file_step + 1

            # Package
            await status("FinalReviewer", f"Step {package_step}/{total_steps} — Validating and packaging...", package_step)

            # Static build validation — check cross-file consistency
            validation_errors = _validate_build(all_files, project_name)
            if validation_errors:
                error_summary = "; ".join(validation_errors[:10])
                await q.put(_sse("agent_message", {
                    "agent": "FinalReviewer",
                    "preview": f"Build validation found {len(validation_errors)} issue(s): {error_summary[:200]}",
                    "step": package_step,
                }))
                logger.warning("Build validation issues: %s", validation_errors)

            src_files  = [f for f in all_files if not f.startswith(f"{project_name}.Tests")]
            test_files = [f for f in all_files if f.startswith(f"{project_name}.Tests")]
            await status("FinalReviewer", f"Complete — {len(src_files)} source + {len(test_files)} test files", package_step)

            zip_bytes = _build_zip(all_files, project_name)
            zip_b64   = base64.b64encode(zip_bytes).decode()

            # Store final artifacts
            if job_id not in _job_artifacts:
                _job_artifacts[job_id] = {"project_name": project_name}
            _job_artifacts[job_id]["final_zip"] = zip_b64

            await q.put(_sse("done", {
                "project_name": project_name,
                "file_count":   len(all_files),
                "src_count":    len(src_files),
                "test_count":   len(test_files),
                "file_list":    list(all_files.keys()),
                "src_files":    src_files,
                "test_files":   test_files,
                "zip_base64":   zip_b64,
                "pre_review_zip_base64": pre_review_b64,
                "pre_review_available": True,
            }))

    except Exception as ex:
        logger.error("CodeGen job %s failed: %s", job_id, ex, exc_info=True)
        await q.put(_sse("error", {"message": str(ex)}))


# -- Endpoints -----------------------------------------------------------------
@router.post("/generate-dotnet", response_model=CodeGenStartResponse)
async def start_codegen(request: CodeGenRequest):
    if not request.open_api_yaml.strip():
        raise HTTPException(status_code=400, detail="OpenAPI YAML is required.")
    job_id = str(uuid.uuid4())
    _job_queues[job_id] = Queue()
    asyncio.create_task(_run_codegen(
        job_id=job_id,
        openapi_yaml=request.open_api_yaml,
        project_name=request.project_name,
        llm_provider=request.llm_provider,
        include_tests=request.include_tests,
    ))
    return CodeGenStartResponse(job_id=job_id, stream_url=f"/api/codegen/stream/{job_id}")


@router.get("/stream/{job_id}")
async def stream_codegen(job_id: str):
    if job_id not in _job_queues:
        raise HTTPException(status_code=404, detail="Job not found.")
    return StreamingResponse(
        _stream_queue(job_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.get("/download/{job_id}/{version}")
async def download_artifact(job_id: str, version: str):
    """Download any version of generated code.
    
    Args:
        job_id: The job identifier
        version: 'pre-review', 'final', 'latest', or 'step-{step_name}' (e.g., 'step-2_solution', 'step-4_entities_dtos')
    """
    # Check incremental files first (for latest/step downloads)
    if version == "latest":
        if job_id in _job_incremental_files and _job_incremental_files[job_id]:
            files = _job_incremental_files[job_id]
            artifacts = _job_artifacts.get(job_id, {})
            project_name = artifacts.get("project_name", "GeneratedApi")
            zip_bytes = _build_zip(files, f"{project_name}_Latest")
            return StreamingResponse(
                io.BytesIO(zip_bytes),
                media_type="application/zip",
                headers={
                    "Content-Disposition": f"attachment; filename={project_name}_Latest.zip",
                    "Content-Length": str(len(zip_bytes)),
                },
            )
        else:
            raise HTTPException(status_code=404, detail="No code generated yet. Please wait for generation to start.")
    
    # Check artifacts storage
    if job_id not in _job_artifacts:
        raise HTTPException(status_code=404, detail="Job artifacts not found or expired.")
    
    artifacts = _job_artifacts[job_id]
    project_name = artifacts["project_name"]
    
    # Handle step-specific downloads
    if version.startswith("step-"):
        step_key = version.replace("step-", "step_")
        zip_b64 = artifacts.get(step_key)
        if zip_b64:
            filename = f"{project_name}_{version}.zip"
        else:
            raise HTTPException(status_code=404, detail=f"Step '{version}' not available yet or not found.")
    elif version == "pre-review":
        zip_b64 = artifacts.get("pre_review_zip")
        filename = f"{project_name}_PreReview.zip"
    elif version == "final":
        zip_b64 = artifacts.get("final_zip")
        filename = f"{project_name}_Final.zip"
    else:
        raise HTTPException(status_code=400, detail="Version must be 'pre-review', 'final', 'latest', or 'step-{step_name}'.")
    
    if not zip_b64:
        raise HTTPException(status_code=404, detail=f"{version} artifact not available yet.")
    
    zip_bytes = base64.b64decode(zip_b64)
    
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Length": str(len(zip_bytes)),
        },
    )


@router.get("/providers")
async def get_providers():
    return {
        "active": getattr(settings, "llm_provider", "groq"),
        "providers": [
            {"id": "groq",   "name": "Groq (LLaMA 70B)", "model": settings.groq_model,                          "available": bool(settings.groq_api_keys)},
            {"id": "openai", "name": "OpenAI (GPT-4o)",   "model": getattr(settings, "openai_model", "gpt-4o"), "available": bool(getattr(settings, "openai_api_key", ""))},
        ],
    }
