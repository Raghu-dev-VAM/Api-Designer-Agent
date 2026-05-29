"""
RAG service for .NET 8 code generation.
Minimal token-efficient contexts per layer.
"""

import os
import logging

logger = logging.getLogger(__name__)
_KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "knowledge")


def _load_file(filename: str) -> str:
    path = os.path.join(_KNOWLEDGE_DIR, filename)
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


_ARCHITECTURE = _load_file("architecture.md")
_BUILD_RULES = _load_file("build_rules.md")


def _extract_section(content: str, header: str) -> str:
    lines = content.split("\n")
    capturing = False
    result = []
    for line in lines:
        if line.strip().startswith("## ") and header.lower() in line.lower():
            capturing = True
            continue
        elif line.strip().startswith("## ") and capturing:
            break
        elif capturing:
            result.append(line)
    return "\n".join(result).strip()


# =============================================================================
# COMPACT RULES - every agent sees these
# =============================================================================

_RULES = """\
STRICT RULES:
- int Id (auto-increment), NOT Guid. NO BaseEntity. NO suffixes (Entity/Dto/Request/Response).
- Namespace = folder path. One class per file. File name = class name.
- ALL string properties initialized = string.Empty; (nullable enabled).
- ALL layers IDENTICAL property names/types. Generate DTOs ONCE (Data model is source of truth) and reuse same properties in all layers.
- Create/Update models: ONLY business fields. NEVER include Id, CreatedAt, UpdatedAt.
- Derived interface (I{Model}Repository) must NOT re-declare methods from IBaseRepository<T>. Keep it empty: public interface I{Model}Repository : IBaseRepository<{Model}> { }
- Interface method names: GetAllAsync(int page, int pageSize, CancellationToken ct = default), GetByIdAsync(int id, CancellationToken ct = default), CreateAsync, UpdateAsync, DeleteAsync. ALL with = default.
- Controller GetAllAsync MUST accept [FromQuery] int page = 1, [FromQuery] int pageSize = 10, CancellationToken ct = default and pass ALL to service.
- Controller [HttpPost] uses Create{Model} type, [HttpPut] uses Update{Model} type. NEVER use the base {Model} type for input.
- CancellationToken MUST have = default in controller signatures (it comes after optional params).
- CancellationToken passed through entire chain: Controller -> Service -> Repository.
- Repository GetAllAsync returns Task<(IEnumerable<T> Items, int TotalCount)> tuple. Service uses this directly. Do NOT call GetCountAsync() — it does not exist.
- Extension ToPagedResult accepts the tuple from repo + page + pageSize. totalCount comes from repo tuple, NOT recomputed.
- Map ALL properties explicitly. NO placeholder comments.
- Extension ToBusinessModel for Create/Update: map ONLY properties that exist on the target model. NEVER map CreatedAt/UpdatedAt (they don't exist on Create/Update models).
- DI modules MUST include using for both Contracts and Repositories namespaces.
- Program.cs: using FluentValidation; AND using FluentValidation.AspNetCore; for AddValidatorsFromAssemblyContaining<T>().
- Program.cs: Each builder.Services call is a SEPARATE statement. AddControllers() returns IMvcBuilder — do NOT chain IServiceCollection methods after it.
- Validators MUST include: using FluentValidation; using {Project}.Presentation.Models;
- Do NOT add [Authorize] or auth code. Do NOT reference AutoMapper. Do NOT register ITokenService/JwtSettings.
- Do NOT use GetProperty("Id").GetValue() in repos. Use _dbSet.FindAsync(id).
"""


# =============================================================================
# PUBLIC API
# =============================================================================

def get_data_layer_context(project_name: str) -> str:
    return f"""{project_name}.Data structure:
- Models/ - plain names, int Id, CreatedAt, UpdatedAt. NO BaseEntity. Strings = string.Empty.
- Contracts/IBaseRepository.cs - generic: GetByIdAsync(int id, CancellationToken ct) returns Task<T?>, GetAllAsync(int page, int pageSize, CancellationToken ct) returns Task<(IEnumerable<T> Items, int TotalCount)>, CreateAsync(T, ct), UpdateAsync(T, ct), DeleteAsync(int id, ct) returns Task<bool>
- Contracts/I{{Model}}Repository.cs - EMPTY interface inheriting IBaseRepository<{{Model}}>. Do NOT re-declare base methods.
- Repositories/BaseRepository.cs - uses _dbSet.FindAsync(id), Skip/Take, Add, Remove, SaveChangesAsync. GetAllAsync returns (items, totalCount) tuple.
- Repositories/{{Model}}Repository.cs - inherits BaseRepository, implements I{{Model}}Repository. Constructor only.
- CompositionModule/DataModule.cs - using {{project}}.Data.Contracts; using {{project}}.Data.Repositories; Registers DbContext + concrete repos.
{_RULES}"""


def get_business_layer_context(project_name: str) -> str:
    return f"""{project_name}.Business structure:
- Models/ - SAME properties as Data. Create{{Model}} and Update{{Model}} exclude Id/CreatedAt/UpdatedAt.
- Extensions/{{Model}}Extensions.cs:
  ToBusinessModel(this Data.Models.{{Model}}) returns Business.Models.{{Model}}
  ToDataModel(this Business.Models.Create{{Model}}) returns Data.Models.{{Model}} (set CreatedAt=UtcNow, UpdatedAt=UtcNow)
  ToPagedResult(this (IEnumerable<Data.Models.{{Model}}> Items, int TotalCount) result, int page, int pageSize) returns Paged{{Model}} — uses result.Items and result.TotalCount from the tuple
- Contracts/I{{Model}}Service.cs - GetAllAsync(int page, int pageSize, CancellationToken ct = default), GetByIdAsync(int id, CancellationToken ct = default), CreateAsync(Create{{Model}}, ct), UpdateAsync(int id, Update{{Model}}, ct), DeleteAsync(int id, ct)
- Services/{{Model}}Service.cs:
  - GetAllAsync: calls _repository.GetAllAsync(page, pageSize, ct) which returns (IEnumerable<T> Items, int TotalCount) tuple. Then call result.ToPagedResult(page, pageSize). Do NOT call GetCountAsync().
  - UpdateAsync: fetch entity, set ONLY properties that exist on Update model (match names exactly), set UpdatedAt=UtcNow, save.
  - Throws KeyNotFoundException when not found.
- CompositionModule/BusinessModule.cs - using Data.CompositionModule; calls AddDataServices, registers services.
{_RULES}"""""


def get_presentation_layer_context(project_name: str) -> str:
    return f"""{project_name}.Presentation structure:
- Models/ - SAME properties as Business. NO Request/Response suffix.
  - Create{{Model}} and Update{{Model}}: ONLY business fields. NEVER include Id, CreatedAt, UpdatedAt.
- Extensions/ - ToBusinessModel(Create{{Model}}) returns Business.Models.Create{{Model}} — map ONLY fields that exist on target. ToApiModel(Business.Models.{{Model}}) returns Presentation.Models.{{Model}} — map ALL fields including Id/CreatedAt/UpdatedAt.
  - CRITICAL: ToBusinessModel for Create/Update must NOT map CreatedAt or UpdatedAt (they don't exist on Business Create/Update models).
- Validators/ - FluentValidation. MUST include: using FluentValidation; using {{project}}.Presentation.Models;
  Program.cs needs: using FluentValidation; using FluentValidation.AspNetCore; then AddFluentValidationAutoValidation() + AddValidatorsFromAssemblyContaining<Create{{Model}}Validator>()
- Controllers/ - [HttpPost] uses Create{{Model}} type, [HttpPut] uses Update{{Model}} type. NEVER use base {{Model}} for input.
  GetAllAsync([FromQuery] int page = 1, [FromQuery] int pageSize = 10, CancellationToken ct = default) — ct MUST have = default.
  NO [Authorize].
- Middleware/ - ExceptionHandling + RequestLogging with static MiddlewareExtensions class.
- Program.cs - NO auth. Each builder.Services.XYZ() is a SEPARATE statement (do not chain). using {{project}}.Business.CompositionModule; using {{project}}.Presentation.Middleware; using FluentValidation; using FluentValidation.AspNetCore;
{_RULES}"""


def get_solution_structure_context(project_name: str) -> str:
    return f"""{project_name} solution: .Data -> .Business -> .Presentation
{_RULES}"""


def get_data_layer_slim(project_name: str) -> str:
    return get_data_layer_context(project_name)


def get_business_layer_slim(project_name: str) -> str:
    return get_business_layer_context(project_name)


def get_presentation_layer_slim(project_name: str) -> str:
    return get_presentation_layer_context(project_name)


def get_build_rules() -> str:
    return _BUILD_RULES


def get_build_rules_section(section: str) -> str:
    return _extract_section(_BUILD_RULES, section)


def get_full_context(project_name: str) -> str:
    return _ARCHITECTURE.replace("{ProjectName}", project_name)


def get_naming_rules() -> str:
    return "Plain names. NO suffixes. Prefixes: Create/Update/Paged. Strings = string.Empty."


def get_folder_rules(layer: str) -> str:
    rules = {
        "data": "CompositionModule/, Models/, Configurations/, Contracts/, Repositories/",
        "business": "CompositionModule/, Models/, Extensions/, Contracts/, Services/",
        "presentation": "Controllers/, Models/, Extensions/, Validators/, Middleware/",
    }
    return rules.get(layer.lower(), "")
