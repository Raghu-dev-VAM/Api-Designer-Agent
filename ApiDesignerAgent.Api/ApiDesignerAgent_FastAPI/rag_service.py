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
- ALL string properties must be initialized: = string.Empty; (nullable enabled)
- ALL layers use IDENTICAL property names and types. If Data has Name (string), Business and Presentation MUST too.
- Interface method names: GetAllAsync, GetByIdAsync, CreateAsync, UpdateAsync, DeleteAsync. Controllers MUST call these exact names.
- CancellationToken MUST be passed through entire chain: Controller -> Service -> Repository.
- Extension method return types must match: ToBusinessModel(CreateX) returns Business.Models.CreateX (NOT the base model).
- Map ALL properties explicitly. NO placeholder comments like '// Set other properties'.
- Do NOT add [Authorize] or auth code - TODO for later.
- Do NOT use AddFluentValidation(). Use: builder.Services.AddFluentValidationAutoValidation(); builder.Services.AddValidatorsFromAssemblyContaining<T>();
- Do NOT use GetProperty("Id").GetValue() in repos. Use FindAsync(id) or EF Core methods.
- Do NOT reference AutoMapper - not used. Do NOT register ITokenService/JwtSettings in DI.
- Register DI dependencies BEFORE services that use them.
"""


# =============================================================================
# PUBLIC API
# =============================================================================

def get_data_layer_context(project_name: str) -> str:
    return f"""{project_name}.Data structure:
- Models/ - DB models (plain names, int Id, CreatedAt, UpdatedAt). NO BaseEntity. Initialize strings = string.Empty.
- Contracts/ - IBaseRepository<T> with methods: GetByIdAsync(int id, CancellationToken ct), GetAllAsync(int page, int pageSize, CancellationToken ct), CreateAsync(T, CancellationToken ct), UpdateAsync(T, CancellationToken ct), DeleteAsync(int id, CancellationToken ct)
- Repositories/ - BaseRepository<T> uses _dbSet.FindAsync(id) for GetById (NOT reflection). Skip/Take for paging.
- Configurations/ - IEntityTypeConfiguration<Model>
- CompositionModule/DataModule.cs - registers DbContext + concrete repos only (NO open generic IBaseRepository)
{_RULES}"""


def get_business_layer_context(project_name: str) -> str:
    return f"""{project_name}.Business structure:
- Models/ - SAME properties as Data model. {project_name}.cs, Create{project_name}.cs, Update{project_name}.cs, Paged{project_name}.cs
- Extensions/ - ToBusinessModel(this Data.Models.X) returns Business.Models.X. ToDataModel(this Business.Models.CreateX) returns Data.Models.X (for insert).
- Contracts/ - I{{Model}}Service with: GetAllAsync(int page, int pageSize, CancellationToken ct), GetByIdAsync(int id, CancellationToken ct), CreateAsync(Create{{Model}}, CancellationToken ct), UpdateAsync(int id, Update{{Model}}, CancellationToken ct), DeleteAsync(int id, CancellationToken ct)
- Services/ - implements interface. Uses {project_name}.Data.Contracts. Passes CancellationToken to repo. Throws KeyNotFoundException.
- CompositionModule/BusinessModule.cs - calls AddDataServices then registers services.
Update: fetch entity, set each property explicitly, save. No ApplyUpdate.
{_RULES}"""


def get_presentation_layer_context(project_name: str) -> str:
    return f"""{project_name}.Presentation structure:
- Models/ - SAME properties as Business model. NO Request/Response suffix.
- Extensions/ - ToBusinessModel(this Presentation.Models.CreateX) returns Business.Models.CreateX (NOT base model). ToApiModel(this Business.Models.X) returns Presentation.Models.X.
- Validators/ - using FluentValidation. AddFluentValidationAutoValidation() + AddValidatorsFromAssemblyContaining<T>() in Program.cs.
- Controllers/ - calls service methods by EXACT name: GetAllAsync, GetByIdAsync, CreateAsync, UpdateAsync, DeleteAsync. Passes CancellationToken. NO [Authorize].
- Middleware/ - ExceptionHandlingMiddleware + RequestLoggingMiddleware with static MiddlewareExtensions class.
- Program.cs - NO auth/JWT. Use app.UseExceptionHandling(), app.UseRequestLogging(). Uses {project_name}.Business.CompositionModule.
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
    return "Plain names. NO suffixes. Prefixes: Create/Update/Paged. Initialize strings = string.Empty."


def get_folder_rules(layer: str) -> str:
    rules = {
        "data": "CompositionModule/, Models/, Configurations/, Contracts/, Repositories/",
        "business": "CompositionModule/, Models/, Extensions/, Contracts/, Services/",
        "presentation": "Controllers/, Models/, Extensions/, Validators/, Middleware/",
    }
    return rules.get(layer.lower(), "")
