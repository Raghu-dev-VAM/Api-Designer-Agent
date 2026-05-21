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
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import settings
from dependencies import get_current_user

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
            msg = await asyncio.wait_for(q.get(), timeout=300)
            yield msg
            if '"event":"done"' in msg or '"event":"error"' in msg:
                break
        except asyncio.TimeoutError:
            yield _sse("error", {"message": "Job timed out"})
            break
    _job_queues.pop(job_id, None)


# -- Fence stripping ----------------------------------------------------------
def _strip_fences(text: str) -> str:
    """Remove ALL markdown code fences from any LLM response."""
    text = text.strip()
    # Remove opening fence line (```csharp, ```json, ```xml, ``` etc)
    text = re.sub(r'^```[a-zA-Z]*\s*\n', '', text)
    # Remove closing fence line
    text = re.sub(r'\n```\s*$', '', text)
    # Remove any remaining standalone fence lines in the middle
    text = re.sub(r'^```[a-zA-Z]*\s*$', '', text, flags=re.MULTILINE)
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
        if path and code:
            files[path] = code
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


# -- Direct LLM call -----------------------------------------------------------
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
    delays = [3, 10, 20]
    attempts = keys * 3

    for i, api_key in enumerate(attempts[:len(delays) * len(keys)]):
        key_preview = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
        try:
            await q.put(_sse("agent_message", {
                "agent": step_label,
                "preview": f"Calling LLM (attempt {i + 1}, key: {key_preview})...",
                "step": step,
            }))
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 8192,
                },
                timeout=120.0,
            )
            if resp.status_code == 429:
                delay = delays[min(i, len(delays) - 1)]
                await q.put(_sse("agent_message", {
                    "agent": step_label,
                    "preview": f"Rate limited (key: {key_preview}) — waiting {delay}s...",
                    "step": step,
                }))
                await asyncio.sleep(delay)
                continue
            if resp.status_code == 401:
                logger.error(f"Invalid API key: {key_preview}")
                await q.put(_sse("agent_message", {
                    "agent": step_label,
                    "preview": f"Invalid API key: {key_preview} — trying next key...",
                    "step": step,
                }))
                continue
            if resp.status_code != 200:
                error_msg = f"Groq {resp.status_code}: {resp.text[:200]}"
                logger.error(f"{error_msg} (key: {key_preview})")
                raise RuntimeError(error_msg)
            content = resp.json()["choices"][0]["message"]["content"]
            await q.put(_sse("agent_message", {
                "agent": step_label,
                "preview": content[:120].replace("\n", " "),
                "step": step,
            }))
            return content
        except httpx.TimeoutException:
            await q.put(_sse("agent_message", {"agent": step_label, "preview": f"Timeout (key: {key_preview}) — retrying...", "step": step}))
            continue
        except RuntimeError:
            raise
        except Exception as ex:
            logger.error("LLM error with key %s: %s", key_preview, ex)
            continue

    raise RuntimeError(f"All LLM attempts failed for: {step_label}. Check API keys in logs.")


# -- .NET 8 Package standards injected into every generation prompt -----------
DOTNET_STANDARDS = """
STRICT .NET 8 PACKAGE AND API STANDARDS — follow exactly:

NuGet packages (use these exact versions):
  <PackageReference Include="Microsoft.AspNetCore.Authentication.JwtBearer" Version="8.0.0" />
  <PackageReference Include="Microsoft.EntityFrameworkCore" Version="8.0.0" />
  <PackageReference Include="Microsoft.EntityFrameworkCore.SqlServer" Version="8.0.0" />
  <PackageReference Include="Microsoft.EntityFrameworkCore.InMemory" Version="8.0.0" />
  <PackageReference Include="Microsoft.EntityFrameworkCore.Tools" Version="8.0.0" />
  <PackageReference Include="AutoMapper.Extensions.Microsoft.DependencyInjection" Version="12.0.1" />
  <PackageReference Include="FluentValidation.AspNetCore" Version="11.3.0" />
  <PackageReference Include="Serilog.AspNetCore" Version="8.0.0" />
  <PackageReference Include="Serilog.Sinks.Console" Version="5.0.0" />
  <PackageReference Include="Serilog.Sinks.File" Version="5.0.0" />
  <PackageReference Include="Swashbuckle.AspNetCore" Version="6.5.0" />
  <PackageReference Include="System.IdentityModel.Tokens.Jwt" Version="7.0.3" />
  <PackageReference Include="Microsoft.AspNetCore.Identity.EntityFrameworkCore" Version="8.0.0" />

Program.cs — use ONLY these current APIs:
  builder.Services.AddControllers()                          // NOT AddMvc()
  builder.Services.AddEndpointsApiExplorer()
  builder.Services.AddSwaggerGen()
  app.UseSwagger()
  app.UseSwaggerUI()
  app.MapControllers()                                       // NOT UseEndpoints()
  app.MapHealthChecks("/health")
  builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme).AddJwtBearer()
  builder.Services.AddAuthorization()
  builder.Services.AddMemoryCache()
  builder.Services.AddRateLimiter()
  builder.Host.UseSerilog()

Using statements — always use:
  using Microsoft.AspNetCore.Authentication.JwtBearer;
  using Microsoft.IdentityModel.Tokens;
  using Microsoft.EntityFrameworkCore;
  using AutoMapper;
  using FluentValidation;
  using Serilog;

DO NOT use:
  - AddNewtonsoftJson (use System.Text.Json built-in)
  - IHostingEnvironment (use IWebHostEnvironment)
  - UseEndpoints (use MapControllers)
  - AddMvc (use AddControllers)
  - app.UseRouting() before MapControllers in .NET 8 minimal hosting
  - Any package version below what is listed above

CRITICAL GENERATION RULES:
1. ENTITY NAMING: Use EXACT entity name consistently everywhere (e.g., if entity is "PersonalDetails", use "PersonalDetails" not "PersonalDetail")
2. ALL PROPERTIES: Entity must have ALL properties that DTOs reference - no missing fields
3. DATA TYPES: Use proper C# types (DateTime for dates, NOT string)
4. USING STATEMENTS: Include ALL required usings at top of EVERY file:
   - using System;
   - using System.Collections.Generic;
   - using System.Linq;
   - using System.Threading;
   - using System.Threading.Tasks;
   - using Microsoft.EntityFrameworkCore; (for EF files)
   - using Microsoft.Extensions.Logging; (for services)
5. EXTENSION METHODS: Generate extension method for EVERY DTO conversion:
   - ToDto(this Entity entity)
   - ToEntity(this CreateDto dto)
   - ToPagedDto(this IEnumerable<Entity> items, int total, int page, int pageSize)
6. REPOSITORY DELETE: DeleteAsync must accept Guid id parameter, NOT entity object
7. INTERFACE IMPLEMENTATIONS: Repository implementations MUST implement their interface (e.g., class PersonalDetailsRepository : IPersonalDetailsRepository)
8. NO BASE CLASSES: Do NOT use BaseEntity or any base class unless explicitly defined
9. COLUMN MAPPING: Property names and column names must match (e.g., ErrorMessage maps to ErrorMessage, NOT StackTrace)
10. PAGING PARAMETERS: ToPagedDto MUST receive (items, totalCount, page, pageSize) - all 4 parameters
11. NO ERROR MODELS: Do NOT generate ErrorRequest, ErrorResponse, or any error-specific models - use exceptions and middleware for error handling
12. DTO REUSE: If CreateDto and UpdateDto have identical properties, generate only CreateDto and reuse it for updates
13. FILE LOCATION: ALL files MUST be generated inside their respective project folders - NO files outside project structure
14. COMPLETE LAYERS: For EVERY controller, generate corresponding service (Business layer) AND repository (Data layer)
"""

# -- Code reviewer -------------------------------------------------------------
REVIEW_SYSTEM = """
You are a strict .NET 8 code reviewer and fixer.
Fix ALL issues below and return ONLY the corrected complete file. No explanation. No markdown fences.

1. DEPRECATED PACKAGES — replace exactly:
   AddNewtonsoftJson()                    -> remove it (System.Text.Json is built-in)
   services.AddMvc()                      -> services.AddControllers()
   app.UseEndpoints(e => e.MapControllers()) -> app.MapControllers()
   IHostingEnvironment                    -> IWebHostEnvironment
   Microsoft.AspNetCore.Mvc.NewtonsoftJson -> remove package reference
   Any EF Core version < 8.0.0            -> Version="8.0.0"
   Any JwtBearer version < 8.0.0          -> Version="8.0.0"
   Any Serilog.AspNetCore version < 8.0.0 -> Version="8.0.0"
   Any AutoMapper version < 12.0.1        -> Version="12.0.1"
   Any FluentValidation version < 11.3.0  -> Version="11.3.0"
   Any Swashbuckle version < 6.5.0        -> Version="6.5.0"

2. BUILD ERRORS — fix:
   - Add ALL missing using statements at top of file
   - Fix namespace to match folder: {project_name}.<Folder>.<SubFolder>
   - Implement ALL interface members (no partial implementations)
   - Fix ALL type mismatches
   - Add missing constructors with proper DI parameters
   - Fix any syntax errors
   - Remove any Error-related request/response models (ErrorRequest, ErrorResponse, etc.)
   - Verify file path starts with project name - if not, correct the path

3. NAMING STANDARDS — enforce:
   - PascalCase: classes, methods, properties, interfaces, enums
   - camelCase: local variables, method parameters
   - _camelCase: private instance fields
   - Interfaces MUST start with I (IUserService not UserService)
   - Async methods MUST end with Async (GetAllAsync not GetAll)
   - Full words only: cancellationToken not ct, repository not repo, request not req

4. CODE QUALITY — enforce:
   - ArgumentNullException.ThrowIfNull(param, nameof(param)) for all constructor params
   - XML doc comments (///) on ALL public classes and methods
   - CancellationToken MUST be last parameter on async methods
   - Remove ALL TODO comments and NotImplementedException
   - ALL async methods MUST return Task or Task<T>
   - No empty catch blocks
   - No hardcoded connection strings or secrets
   - Remove duplicate service interfaces/implementations (e.g., if IPersonalDetailsService appears twice)
   - Consolidate identical Create/Update DTOs with XML remarks about reusability

5. CRITICAL FILE LOCATION FIXES — if file path is wrong, SKIP this file and mark for regeneration:
   BUSINESS PROJECT:
   - Service interfaces MUST be in: {project_name}.Business/Services/Interfaces/
   - Service implementations MUST be in: {project_name}.Business/Services/Implementations/
   - DTOs MUST be in: {project_name}.Business/DTOs/
   - Extensions MUST be in: {project_name}.Business/Extensions/
   - DO NOT allow: {project_name}.Business/I*Service.cs (wrong location)
   - DO NOT allow: {project_name}.Business/*Service.cs (wrong location)
   - DO NOT allow: {project_name}.Business/I*Repository.cs (belongs in Data project)
   - DO NOT allow: {project_name}.Business/*Repository.cs (belongs in Data project)
   
   DATA PROJECT:
   - Repository interfaces MUST be in: {project_name}.Data/Repositories/Interfaces/
   - Repository implementations MUST be in: {project_name}.Data/Repositories/Implementations/
   - Entities MUST be in: {project_name}.Data/Entities/
   - Configurations MUST be in: {project_name}.Data/Configurations/
   - DO NOT allow: {project_name}.Data/I*Repository.cs (wrong location)
   - DO NOT allow: {project_name}.Data/*Repository.cs (wrong location)
   - DO NOT allow: {project_name}.Data/I*Service.cs (belongs in Business project)
   - DO NOT allow: {project_name}.Data/*Service.cs (belongs in Business project)
   
   PRESENTATION PROJECT:
   - Controllers MUST be in: {project_name}.Presentation/Controllers/
   - Request models MUST be in: {project_name}.Presentation/Models/Requests/
   - Response models MUST be in: {project_name}.Presentation/Models/Responses/
   - Extensions MUST be in: {project_name}.Presentation/Extensions/
   - DO NOT allow: {project_name}.Presentation/*Controller.cs (wrong location)
   - DO NOT allow: {project_name}.Presentation/*Request.cs (wrong location)
   - DO NOT allow: {project_name}.Presentation/*Response.cs (wrong location)
   - DO NOT allow: {project_name}.Presentation/*Extensions.cs (wrong location)

6. IF FILE IS IN WRONG LOCATION:
   - Return comment: // SKIP: File in wrong location. Should be in [correct path]
   - Do NOT attempt to fix the file
   - Let regeneration handle it

Return ONLY the fixed file content. No markdown fences. No explanation.
If file is in wrong location, return: // SKIP: File in wrong location. Should be in [correct path]
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

    for i, (path, code) in enumerate(cs_files.items()):
        await q.put(_sse("agent_message", {
            "agent": "SeniorReviewer",
            "preview": f"Reviewing {path} ({i + 1}/{total})...",
            "step": step,
        }))
        try:
            result = await _llm(
                client,
                system=REVIEW_SYSTEM.replace("{project_name}", project_name),
                user=f"File: {path}\n\n{code}",
                step_label="SeniorReviewer",
                keys=keys, model=model, q=q, step=step,
            )
            cleaned_result = _strip_fences(result)
            
            # Check if file was marked for skipping due to wrong location
            if cleaned_result.strip().startswith("// SKIP:"):
                logger.warning(f"Skipping file in wrong location: {path} - {cleaned_result}")
                skipped_files.append(path)
                # Don't include this file in the output
                continue
            
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

        async with httpx.AsyncClient(timeout=120.0) as client:

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

            # Step 2: Solution + project files
            await status("Coder", f"Step 2/{total_steps} — Generating solution and project files...", 2)
            tests_section = (
                f"5. {project_name}.Tests/{project_name}.Tests.csproj — xUnit test project:\n"
                f"   xunit, Moq, Microsoft.AspNetCore.Mvc.Testing, Microsoft.EntityFrameworkCore.InMemory,\n"
                f"   FluentAssertions, ProjectReference to {project_name}.Presentation\n\n"
            ) if include_tests else ""

            proj_text = await _llm(
                client,
                system="""You are a senior .NET 8 developer.
Generate COMPLETE files using EXACTLY this format:
=== FILE: <path> ===
<complete code>
=== END FILE ===
No explanation outside file blocks.""",
                user=f"""{DOTNET_STANDARDS}
Generate a clean architecture solution for '{project_name}':

1. {project_name}.sln — solution file referencing all projects

2. {project_name}.Data/{project_name}.Data.csproj — class library:
   Microsoft.EntityFrameworkCore 8.0.0, Microsoft.EntityFrameworkCore.SqlServer 8.0.0,
   Microsoft.EntityFrameworkCore.InMemory 8.0.0, Microsoft.EntityFrameworkCore.Tools 8.0.0

3. {project_name}.Business/{project_name}.Business.csproj — class library:
   AutoMapper.Extensions.Microsoft.DependencyInjection 12.0.1, FluentValidation 11.3.0,
   ProjectReference to {project_name}.Data

4. {project_name}.Presentation/{project_name}.Presentation.csproj — ASP.NET Core Web API:
   Microsoft.AspNetCore.Authentication.JwtBearer 8.0.0, Swashbuckle.AspNetCore 6.5.0,
   Serilog.AspNetCore 8.0.0, Serilog.Sinks.Console 5.0.0, Serilog.Sinks.File 5.0.0,
   System.IdentityModel.Tokens.Jwt 7.0.3,
   ProjectReference to {project_name}.Business

{tests_section}5. {project_name}.Presentation/appsettings.json — JWT, Serilog, ConnectionStrings sections
6. {project_name}.Presentation/appsettings.Development.json — dev overrides with InMemory db
7. README.md — solution structure and setup instructions""",
                step_label="Coder", keys=keys, model=model, q=q, step=2,
            )
            extracted_proj_files = _extract_files(proj_text)
            if f"{project_name}.sln" in extracted_proj_files:
                extracted_proj_files[f"{project_name}.sln"] = _ensure_sln_endproject(extracted_proj_files[f"{project_name}.sln"])
            all_files.update(extracted_proj_files)
            await status("Coder", f"Solution files done ({len(all_files)} files so far)", 2)
            await save_incremental("2_solution")

            # Step 3: Auth & Security (Presentation project)
            await status("SecurityExpert", f"Step 3/{total_steps} — Generating JWT auth, middleware (Presentation)...", 3)
            auth_text = await _llm(
                client,
                system="""You are a .NET 8 security architect.
Generate COMPLETE C# files using EXACTLY this format:
=== FILE: <path> ===
<complete code>
=== END FILE ===
Full implementations. No TODOs.""",
                user=f"""{DOTNET_STANDARDS}
Generate security files inside '{project_name}.Presentation' project:
1. {project_name}.Presentation/Auth/JwtSettings.cs — namespace {project_name}.Presentation.Auth
2. {project_name}.Presentation/Auth/ITokenService.cs — interface: GenerateAccessToken, GenerateRefreshToken, GetPrincipalFromExpiredToken
3. {project_name}.Presentation/Auth/JwtTokenService.cs — full JWT + refresh token HMAC-SHA256
4. {project_name}.Presentation/Auth/TokenRequest.cs — Email, Password
5. {project_name}.Presentation/Auth/TokenResponse.cs — AccessToken, RefreshToken, ExpiresAt
6. {project_name}.Presentation/Middleware/ExceptionHandlingMiddleware.cs — ProblemDetails RFC 7807
7. {project_name}.Presentation/Middleware/RequestLoggingMiddleware.cs — Serilog logging
8. {project_name}.Presentation/Extensions/ServiceCollectionExtensions.cs — register JWT, Swagger with bearer, rate limiting, CORS""",
                step_label="SecurityExpert", keys=keys, model=model, q=q, step=3,
            )
            all_files.update(_extract_files(auth_text))
            await status("SecurityExpert", f"Auth files done ({len(all_files)} files so far)", 3)
            await save_incremental("3_auth")

            # Step 4: Entities (Data) + DTOs per layer + extension converters
            await status("Coder", f"Step 4/{total_steps} — Generating entities, DTOs per layer, extension converters...", 4)
            for entity in entities[:3]:
                model_text = await _llm(
                    client,
                    system="""You are a senior .NET 8 developer.
Generate COMPLETE C# files using EXACTLY this format:
=== FILE: <path> ===
<complete code>
=== END FILE ===

CRITICAL REQUIREMENTS:
1. Use EXACT entity name consistently (if entity is "PersonalDetails", use "PersonalDetails" everywhere, NOT "PersonalDetail")
2. Include ALL required using statements at top of EVERY file
3. Use proper C# types (DateTime for dates, int for numbers, NOT string)
4. Generate ALL extension methods for EVERY DTO
5. Entity must have ALL properties that DTOs reference
6. NO base classes unless explicitly defined
7. DO NOT generate any Error-related models (ErrorRequest, ErrorResponse, etc.) - use exceptions
8. If Create and Update DTOs have same properties, generate only CreateDto and add a note to reuse it
9. ALL files MUST be inside project folders - verify paths start with project name
Full implementations. No TODOs.""",
                    user=f"""Generate files for entity '{entity}' across all projects:

CRITICAL FILE LOCATION RULES:
- ALL files MUST be inside their respective project folders
- NEVER create files at project root level
- ALWAYS include full path with folder structure
- Verify path starts with {project_name}.<ProjectName>/

IMPORTANT: Use entity name "{entity}" EXACTLY as-is in ALL files. Do NOT change singular/plural.

DATA PROJECT — {project_name}.Data:
1. {project_name}.Data/Entities/{entity}.cs — EF Core entity, namespace {project_name}.Data.Entities
   CRITICAL: File MUST be inside Entities folder
   Required usings: using System; using System.ComponentModel.DataAnnotations;
   Properties: Id (Guid), CreatedAt (DateTime), UpdatedAt (DateTime), CreatedBy (string) + all business fields from spec
   Use proper types: DateTime for dates, decimal for money, int for numbers

BUSINESS PROJECT — {project_name}.Business:
2. {project_name}.Business/DTOs/{entity}Dto.cs — business layer DTO, namespace {project_name}.Business.DTOs
   CRITICAL: File MUST be inside DTOs folder
   Required usings: using System;
   All public properties matching entity with SAME types
3. {project_name}.Business/DTOs/Create{entity}Dto.cs — create input DTO with FluentValidation AbstractValidator
   CRITICAL: File MUST be inside DTOs folder
   Required usings: using System; using FluentValidation;
   Use proper types matching entity
   IMPORTANT: Compare properties with Update - if identical, add XML comment: "/// <remarks>This DTO can be reused for Update operations</remarks>"
4. {project_name}.Business/DTOs/Update{entity}Dto.cs — update input DTO with FluentValidation AbstractValidator
   CRITICAL: File MUST be inside DTOs folder
   Required usings: using System; using FluentValidation;
   Use proper types matching entity
   IMPORTANT: If properties match CreateDto exactly, you may skip this file and add comment in CreateDto to reuse it
5. {project_name}.Business/DTOs/Paged{entity}Dto.cs — paged result
   CRITICAL: File MUST be inside DTOs folder
   Required usings: using System; using System.Collections.Generic;
   Properties: Items (List<{entity}Dto>), TotalCount (int), Page (int), PageSize (int), TotalPages (int)
6. {project_name}.Business/Extensions/{entity}MappingExtensions.cs — static extension methods:
   CRITICAL: File MUST be inside Extensions folder
   Required usings: using System; using System.Collections.Generic; using System.Linq; using {project_name}.Data.Entities; using {project_name}.Business.DTOs;
   MUST generate ALL these methods:
   - public static {entity}Dto ToDto(this {entity} entity)
   - public static {entity} ToEntity(this Create{entity}Dto dto)
   - public static {entity} ApplyUpdate(this {entity} entity, Update{entity}Dto dto)
   - public static Paged{entity}Dto ToPagedDto(this IEnumerable<{entity}> items, int totalCount, int page, int pageSize)

PRESENTATION PROJECT — {project_name}.Presentation:
7. {project_name}.Presentation/Models/Requests/Create{entity}Request.cs — API request model with FluentValidation
   CRITICAL: File MUST be inside Models/Requests folder
   Required usings: using System; using FluentValidation;
   IMPORTANT: If properties match Update, add XML comment: "/// <remarks>This request can be reused for Update operations</remarks>"
8. {project_name}.Presentation/Models/Requests/Update{entity}Request.cs — API request model with FluentValidation
   CRITICAL: File MUST be inside Models/Requests folder
   Required usings: using System; using FluentValidation;
   IMPORTANT: If properties match CreateRequest exactly, you may skip this file and reuse CreateRequest
   DO NOT generate ErrorRequest or ErrorResponse models - errors handled by middleware
9. {project_name}.Presentation/Models/Responses/{entity}Response.cs — API response model
   CRITICAL: File MUST be inside Models/Responses folder
   Required usings: using System;
10. {project_name}.Presentation/Models/Responses/Paged{entity}Response.cs — paged API response
    CRITICAL: File MUST be inside Models/Responses folder
    Required usings: using System; using System.Collections.Generic;
11. {project_name}.Presentation/Extensions/{entity}RequestExtensions.cs — static extension methods:
    CRITICAL: File MUST be inside Extensions folder
    Required usings: using System; using System.Collections.Generic; using System.Linq; using {project_name}.Business.DTOs; using {project_name}.Presentation.Models.Requests; using {project_name}.Presentation.Models.Responses;
    MUST generate ALL these methods:
    - public static Create{entity}Dto ToCreateDto(this Create{entity}Request request)
    - public static Update{entity}Dto ToUpdateDto(this Update{entity}Request request)
    - public static {entity}Response ToResponse(this {entity}Dto dto)
    - public static Paged{entity}Response ToPagedResponse(this Paged{entity}Dto paged)

OpenAPI context:
{openapi_yaml[:1500]}""",
                    step_label="Coder", keys=keys, model=model, q=q, step=4,
                )
                all_files.update(_extract_files(model_text))
            await status("Coder", f"Entities + DTOs done ({len(all_files)} files so far)", 4)
            await save_incremental("4_entities_dtos")

            # Step 5: DbContext + Repositories (Data project)
            await status("Coder", f"Step 5/{total_steps} — Generating DbContext and repositories (Data project)...", 5)
            
            # Generate configurations for available entities (up to 3)
            config_prompts = []
            for idx, entity in enumerate(entities[:3], 1):
                # Build the configuration prompt without backslashes in f-string
                using_stmt = f"using Microsoft.EntityFrameworkCore; using Microsoft.EntityFrameworkCore.Metadata.Builders; using {project_name}.Data.Entities;"
                config_prompts.append(
                    f"{idx+1}. {project_name}.Data/Configurations/{entity}Configuration.cs — namespace {project_name}.Data.Configurations\n"
                    f"   class {entity}Configuration : IEntityTypeConfiguration<{entity}>\n"
                    f"   include table mapping, primary key, indexes, and constraints"
                )
            
            # Build the using statement separately to avoid backslash in f-string
            required_usings = f"using Microsoft.EntityFrameworkCore; using Microsoft.EntityFrameworkCore.Metadata.Builders; using {project_name}.Data.Entities;"
            config_prompts_joined = "\n".join(config_prompts)
            
            db_text = await _llm(
                client,
                system="""You are a senior .NET 8 developer.
Generate COMPLETE C# files using EXACTLY this format:
=== FILE: <path> ===
<complete code>
=== END FILE ===

CRITICAL REQUIREMENTS:
1. Include ALL required using statements at top of EVERY file
2. Use entity names EXACTLY as provided
3. NO base classes (no BaseEntity)
4. Property names and column names must match exactly
Full implementations. No TODOs.""",
                user=f"""Generate Data project infrastructure files for '{project_name}.Data':
1. {project_name}.Data/AppDbContext.cs — namespace {project_name}.Data
   Required usings: using System; using System.Threading; using System.Threading.Tasks; using Microsoft.EntityFrameworkCore; using {project_name}.Data.Entities; using {project_name}.Data.Configurations;
   Contains a single AppDbContext class only (no other classes in this file)
   Add DbSet<{entities[0]}> properties for all entities: {', '.join(entities[:3])}
   OnModelCreating applies configuration classes with modelBuilder.ApplyConfiguration(new {entities[0]}Configuration())
   SaveChangesAsync override sets CreatedAt/UpdatedAt automatically
   DO NOT use BaseEntity or any base class
{config_prompts_joined}
   Each configuration must include required usings: {required_usings}""",
                step_label="Coder", keys=keys, model=model, q=q, step=5,
            )
            all_files.update(_extract_files(db_text))

            for entity in entities[:3]:
                repo_text = await _llm(
                    client,
                    system="""You are a senior .NET 8 developer.
Generate COMPLETE C# files using EXACTLY this format:
=== FILE: <path> ===
<complete code>
=== END FILE ===

CRITICAL REQUIREMENTS:
1. Include ALL required using statements
2. Repository class MUST implement its interface
3. DeleteAsync accepts Guid id parameter, NOT entity object
4. Use entity name EXACTLY as provided
Full implementations. No TODOs.""",
                    user=f"""Generate Data project repository files for '{entity}' in '{project_name}.Data':

CRITICAL FILE LOCATION RULES:
- Repository interface MUST be in Repositories/Interfaces folder
- Repository implementation MUST be in Repositories/Implementations folder
- DO NOT create repository files at Data project root
- DO NOT create service interfaces or implementations in Data project (they belong in Business project)
- Verify full path includes folder structure

1. {project_name}.Data/Repositories/Interfaces/I{entity}Repository.cs — namespace {project_name}.Data.Repositories
   CRITICAL: File MUST be inside Repositories/Interfaces folder
   Required usings: using System; using System.Collections.Generic; using System.Threading; using System.Threading.Tasks; using {project_name}.Data.Entities;
   Methods:
   GetByIdAsync(Guid id, CancellationToken cancellationToken) -> Task<{entity}?>
   GetAllAsync(int page, int pageSize, CancellationToken cancellationToken) -> Task<(IEnumerable<{entity}> items, int total)>
   CreateAsync({entity} entity, CancellationToken cancellationToken) -> Task<{entity}>
   UpdateAsync({entity} entity, CancellationToken cancellationToken) -> Task<{entity}>
   DeleteAsync(Guid id, CancellationToken cancellationToken) -> Task<bool>
   ExistsAsync(Guid id, CancellationToken cancellationToken) -> Task<bool>

2. {project_name}.Data/Repositories/Implementations/{entity}Repository.cs — namespace {project_name}.Data.Repositories
   CRITICAL: File MUST be inside Repositories/Implementations folder
   Required usings: using System; using System.Collections.Generic; using System.Linq; using System.Threading; using System.Threading.Tasks; using Microsoft.EntityFrameworkCore; using {project_name}.Data.Entities;
   MUST implement I{entity}Repository interface: public class {entity}Repository : I{entity}Repository
   Full EF Core implementation using AppDbContext, async/await, Skip/Take pagination
   DeleteAsync implementation: find entity by id, then delete it

DO NOT GENERATE:
- Service interfaces (they belong in Business project)
- Service implementations (they belong in Business project)
- Any files outside Repositories/Interfaces or Repositories/Implementations folders""",
                    step_label="Coder", keys=keys, model=model, q=q, step=5,
                )
                all_files.update(_extract_files(repo_text))

            data_ext_text = await _llm(
                client,
                system="""You are a senior .NET 8 developer.
Generate COMPLETE C# files using EXACTLY this format:
=== FILE: <path> ===
<complete code>
=== END FILE ===

CRITICAL REQUIREMENTS:
1. Include ALL required using statements
2. Register ONLY interfaces and implementations that were actually generated
3. Use AddScoped for repositories
Full implementations. No TODOs.""",
                user=f"""Generate Data project extension files for '{project_name}.Data':
1. {project_name}.Data/Extensions/DataServiceExtensions.cs — namespace {project_name}.Data.Extensions
   Required usings: using Microsoft.EntityFrameworkCore; using Microsoft.Extensions.Configuration; using Microsoft.Extensions.DependencyInjection; using {project_name}.Data; using {project_name}.Data.Repositories;
   static AddDataServices(this IServiceCollection services, IConfiguration configuration)
   Register AppDbContext with SQL Server
   Register repository implementations for entities: {', '.join(entities[:3])}
   Example: services.AddScoped<I{entities[0]}Repository, {entities[0]}Repository>();
   ONLY register repositories that were generated, do NOT add unknown interfaces""",
                step_label="Coder", keys=keys, model=model, q=q, step=5,
            )
            all_files.update(_extract_files(data_ext_text))
            await status("Coder", f"Data project done ({len(all_files)} files so far)", 5)
            await save_incremental("5_data_layer")

            # Step 6: Business services
            await status("Coder", f"Step 6/{total_steps} — Generating business services (Business project)...", 6)
            for entity in entities[:3]:
                svc_text = await _llm(
                    client,
                    system="""You are a senior .NET 8 developer.
Generate COMPLETE C# files using EXACTLY this format:
=== FILE: <path> ===
<complete code>
=== END FILE ===

CRITICAL REQUIREMENTS:
1. Include ALL required using statements
2. Use extension methods for ALL DTO conversions
3. Call ToPagedDto with ALL 4 parameters: (items, totalCount, page, pageSize)
4. DeleteAsync calls repository.DeleteAsync(id) with Guid id, NOT entity
5. Use entity name EXACTLY as provided
Full business logic. No TODOs.""",
                    user=f"""Generate Business project service files for '{entity}' in '{project_name}.Business':

CRITICAL FILE LOCATION RULES:
- Service interface MUST be in Services/Interfaces folder
- Service implementation MUST be in Services/Implementations folder
- DO NOT create service files at Business project root
- DO NOT create repository interfaces or implementations in Business project (they belong in Data project)
- Verify full path includes folder structure

1. {project_name}.Business/Services/Interfaces/I{entity}Service.cs — namespace {project_name}.Business.Services
   CRITICAL: File MUST be inside Services/Interfaces folder
   Required usings: using System; using System.Threading; using System.Threading.Tasks; using {project_name}.Business.DTOs;
   Methods:
   GetAllAsync(int page, int pageSize, CancellationToken cancellationToken) -> Task<Paged{entity}Dto>
   GetByIdAsync(Guid id, CancellationToken cancellationToken) -> Task<{entity}Dto>
   CreateAsync(Create{entity}Dto dto, CancellationToken cancellationToken) -> Task<{entity}Dto>
   UpdateAsync(Guid id, Update{entity}Dto dto, CancellationToken cancellationToken) -> Task<{entity}Dto>
   DeleteAsync(Guid id, CancellationToken cancellationToken) -> Task

2. {project_name}.Business/Services/Implementations/{entity}Service.cs — namespace {project_name}.Business.Services
   CRITICAL: File MUST be inside Services/Implementations folder
   Required usings: using System; using System.Collections.Generic; using System.Linq; using System.Threading; using System.Threading.Tasks; using Microsoft.Extensions.Logging; using {project_name}.Data.Repositories; using {project_name}.Business.DTOs; using {project_name}.Business.Extensions;
   Constructor: I{entity}Repository repository, ILogger<{entity}Service> logger
   Use {entity}MappingExtensions extension methods for all conversions:
   - entity.ToDto()
   - dto.ToEntity()
   - entity.ApplyUpdate(dto)
   - items.ToPagedDto(totalCount, page, pageSize) — MUST pass all 4 parameters
   DeleteAsync implementation: await _repository.DeleteAsync(id, cancellationToken); — pass Guid id, NOT entity
   Throw KeyNotFoundException when entity not found
   Log every operation with structured logging

DO NOT GENERATE:
- Repository interfaces (they belong in Data project)
- Repository implementations (they belong in Data project)
- Any files outside Services/Interfaces or Services/Implementations folders""",
                    step_label="Coder", keys=keys, model=model, q=q, step=6,
                )
                all_files.update(_extract_files(svc_text))

            business_ext_text = await _llm(
                client,
                system="""You are a senior .NET 8 developer.
Generate COMPLETE C# files using EXACTLY this format:
=== FILE: <path> ===
<complete code>
=== END FILE ===

CRITICAL REQUIREMENTS:
1. Include ALL required using statements
2. Register ONLY services that were actually generated
3. Use AddScoped for services
Full implementations. No TODOs.""",
                user=f"""Generate Business project extension files for '{project_name}.Business':
1. {project_name}.Business/Extensions/BusinessServiceExtensions.cs — namespace {project_name}.Business.Extensions
   Required usings: using Microsoft.Extensions.Configuration; using Microsoft.Extensions.DependencyInjection; using {project_name}.Data.Extensions; using {project_name}.Business.Services;
   static AddBusinessServices(this IServiceCollection services, IConfiguration configuration)
   call services.AddDataServices(configuration)
   register all service implementations for entities: {', '.join(entities[:3])}
   Example: services.AddScoped<I{entities[0]}Service, {entities[0]}Service>();
   ONLY register services that were generated, do NOT add unknown interfaces""",
                step_label="Coder", keys=keys, model=model, q=q, step=6,
            )
            all_files.update(_extract_files(business_ext_text))
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
                ctrl_text = await _llm(
                    client,
                    system="""You are a senior .NET 8 Web API developer.
Generate COMPLETE C# files using EXACTLY this format:
=== FILE: <path> ===
<complete code>
=== END FILE ===
Production-ready. No TODOs. Full XML doc comments.""",
                    user=f"""Generate controller for '{entity}' in '{project_name}.Presentation':

CRITICAL FILE LOCATION RULES:
- Controller MUST be in Controllers folder
- DO NOT create controller at Presentation project root
- Verify full path: {project_name}.Presentation/Controllers/{ctrl}Controller.cs

{project_name}.Presentation/Controllers/{ctrl}Controller.cs — namespace {project_name}.Presentation.Controllers
- CRITICAL: File MUST be inside Controllers folder
- [ApiController], [Route("api/[controller]")]
- Constructor: I{entity}Service service, ILogger<{ctrl}Controller> logger
- GET / — GetAllAsync([FromQuery] int page=1, [FromQuery] int pageSize=10, CancellationToken cancellationToken)
  [AllowAnonymous], returns Paged{entity}Response
  Use: var result = await _service.GetAllAsync(page, pageSize, cancellationToken); return Ok(result.ToPagedResponse());
- GET /{{id}} — GetByIdAsync(Guid id, CancellationToken cancellationToken)
  [AllowAnonymous], returns {entity}Response
  Use: var result = await _service.GetByIdAsync(id, cancellationToken); return Ok(result.ToResponse());
- POST / — CreateAsync([FromBody] Create{entity}Request request, CancellationToken cancellationToken)
  [Authorize(Roles="Admin,User")], returns 201 Created with {entity}Response
  Use: var dto = request.ToCreateDto(); var result = await _service.CreateAsync(dto, cancellationToken); return CreatedAtAction(...);
- PUT /{{id}} — UpdateAsync(Guid id, [FromBody] Update{entity}Request request, CancellationToken cancellationToken)
  [Authorize(Roles="Admin,User")], returns {entity}Response
  Use: var dto = request.ToUpdateDto(); var result = await _service.UpdateAsync(id, dto, cancellationToken); return Ok(result.ToResponse());
- DELETE /{{id}} — DeleteAsync(Guid id, CancellationToken cancellationToken)
  [Authorize(Roles="Admin")], returns 204 NoContent
- Catch KeyNotFoundException -> return NotFound()
- ProducesResponseType for 200,201,204,400,401,403,404,500

DO NOT create controller files outside Controllers folder""",
                    step_label="Coder", keys=keys, model=model, q=q, step=7,
                )
                all_files.update(_extract_files(ctrl_text))
            await status("Coder", f"Controllers done ({len(all_files)} files so far)", 7)
            await save_incremental("7_controllers")

            # Step 8: Program.cs (Presentation project)
            await status("Coder", f"Step 8/{total_steps} — Generating Program.cs (Presentation project)...", 8)
            prog_text = await _llm(
                client,
                system="""You are a senior .NET 8 developer.
Generate COMPLETE C# files using EXACTLY this format:
=== FILE: <path> ===
<complete code>
=== END FILE ===
Full production-ready Program.cs. No TODOs.""",
                user=f"""{DOTNET_STANDARDS}
Generate {project_name}.Presentation/Program.cs — namespace {project_name}.Presentation:

Must call in order:
  builder.Host.UseSerilog()
  builder.Services.AddBusinessServices(builder.Configuration)   // from {project_name}.Business
  builder.Services.AddControllers()
  builder.Services.AddEndpointsApiExplorer()
  builder.Services.AddSwaggerGen() with JWT bearer security
  builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme).AddJwtBearer()
  builder.Services.AddAuthorization() with Admin/User/ReadOnly policies
  builder.Services.AddRateLimiter()
  builder.Services.AddHealthChecks()
  builder.Services.AddSingleton<ITokenService, JwtTokenService>()

  app.UseExceptionHandlingMiddleware()
  app.UseRequestLoggingMiddleware()
  app.UseHttpsRedirection()
  app.UseAuthentication()
  app.UseAuthorization()
  app.UseRateLimiter()
  app.UseSwagger()
  app.UseSwaggerUI()
  app.MapControllers()
  app.MapHealthChecks("/health")

Entities: {', '.join(entities)}
Controllers: {', '.join(controllers)}""",
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
            await status("FinalReviewer", f"Step {package_step}/{total_steps} — Packaging all files...", package_step)
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
                "pre_review_available": True,
                "download_urls": {
                    "pre_review": f"/api/codegen/download/{job_id}/pre-review",
                    "final": f"/api/codegen/download/{job_id}/final",
                    "latest": f"/api/codegen/download/{job_id}/latest",
                },
            }))

    except Exception as ex:
        logger.error("CodeGen job %s failed: %s", job_id, ex, exc_info=True)
        await q.put(_sse("error", {"message": str(ex)}))


# -- Endpoints -----------------------------------------------------------------
@router.post("/generate-dotnet", response_model=CodeGenStartResponse)
async def start_codegen(request: CodeGenRequest, _: dict = Depends(get_current_user)):
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
async def download_artifact(job_id: str, version: str, _: dict = Depends(get_current_user)):
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
