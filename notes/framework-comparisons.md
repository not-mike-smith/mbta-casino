# Framework Comparisons

Personal reference notes mapping concepts in this stack to tools you already know.

## Django Migrations vs. EF/Pomelo

| Concept | EF / Pomelo | Django |
| ------- | ----------- | ------ |
| Generate migration from model changes | `dotnet ef migrations add <Name>` | `manage.py makemigrations` |
| Apply pending migrations to DB | `dotnet ef database update` | `manage.py migrate` |
| Rollback to a specific migration | `dotnet ef database update <Name>` | `manage.py migrate <app_label> <migration_name>` |
| Migration files | C# classes in `Migrations/` | Python files in `<app>/migrations/` |
| Auto-apply on startup | Configurable (common pattern) | Never — always an explicit command |

Key difference: Django migrations are always an explicit step. The application will start and run against the database regardless of whether migrations are pending — there is no startup check.

## Python Structured Logging (`structlog`) vs. .NET `ILogger` with `BeginScope`

`structlog` is the Python library that most closely maps to .NET's `ILogger` with structured logging and scopes.

| Concept | .NET `ILogger` | `structlog` |
| ------- | -------------- | ----------- |
| Log with structured fields | `logger.LogInformation("Bet placed {BetId}", id)` | `log.info("bet_placed", bet_id=id)` |
| Attach fields to all logs in a scope | `logger.BeginScope(new { UserId = id })` | `structlog.contextvars.bind_contextvars(user_id=id)` |
| Clear scope context | Dispose the scope | `structlog.contextvars.clear_contextvars()` |
| JSON output in production | Configure with `JsonFormatter` | Configure with `structlog.processors.JSONRenderer()` |
| Human-readable output in dev | Configure with `SimpleConsoleFormatter` | Configure with `structlog.dev.ConsoleRenderer()` |

`bind_contextvars` binds fields to the current async/thread context, so any log call made after binding automatically includes those fields — equivalent to wrapping code in a `BeginScope` block.
