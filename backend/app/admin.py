from typing import Any
from decimal import Decimal
import json
from io import StringIO

from starlette.requests import Request
from starlette.responses import Response, RedirectResponse
from starlette_admin.views import CustomView
from starlette_admin.exceptions import FormValidationError
from sqlmodel import Session
from starlette.templating import Jinja2Templates

from app.core.db import engine
from app.models import Task, TaskCreate, FlexibleBulkImportRequest


class FlexibleBulkImportView(CustomView):
    """Custom admin view for flexible JSONL import with field mapping"""

    def __init__(self):
        super().__init__(
            label="Bulk Import",
            icon="fa fa-magic",
            path="/flexible-bulk-import",
            template_path="flexible_import.html",
            name="flexible-bulk-import",
            methods=["GET", "POST"],
            add_to_menu=True
        )
    def is_accessible(self, request: Request) -> bool:
        """Only allow access to authenticated admin users"""
        return request.session.get("admin_user") is not None

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        """Handle both GET and POST requests"""
        if request.method == "GET":
            return await self._render_form(request, templates, {})
        elif request.method == "POST":
            return await self.handle_upload(request, templates)
        else:
            return Response("Method not allowed", status_code=405)

    async def _render_form(self, request: Request, templates: Jinja2Templates, params: dict[str, Any]) -> Response:
        """Render the flexible import form"""
        context = {
            "request": request,
            "view": self,
            "title": self.title(request),
            "success_message": params.get("success_message"),
            "error_message": params.get("error_message"),
            "import_results": params.get("import_results"),
        }
        return templates.TemplateResponse(self.template_path, context)

    async def handle_upload(self, request: Request, templates: Jinja2Templates) -> Response:
        """Handle flexible JSONL file upload and process with field mapping"""
        try:
            form = await request.form()
            file = form.get("jsonl_file")

            # Helper function to get field value (custom input takes precedence over dropdown)
            def get_field_value(field_name):
                custom_value = form.get(f"{field_name}_custom")
                if custom_value and custom_value.strip():
                    return custom_value.strip()
                dropdown_value = form.get(field_name)
                return dropdown_value if dropdown_value else None

            # Helper function to get multiple content fields
            def get_content_fields():
                custom_value = form.get("content_field_custom")
                if custom_value and custom_value.strip():
                    # Parse custom textarea input (one field per line)
                    fields = [f.strip() for f in custom_value.strip().split('\n') if f.strip()]
                    return fields
                
                # Get selected values from multi-select dropdown
                content_fields = form.getlist("content_field")
                # Filter out empty values
                return [f for f in content_fields if f and f.strip()]

            # Required field mapping - now supports multiple content fields
            content_fields = get_content_fields()
            if not content_fields:
                raise FormValidationError("At least one content field mapping is required")

            # Optional field mappings
            title_field = get_field_value("title_field")
            description_field = get_field_value("description_field")
            source_language_field = get_field_value("source_language_field")
            target_language_field = get_field_value("target_language_field")
            reward_amount_field = get_field_value("reward_amount_field")

            # Default values
            default_source_language = form.get("default_source_language", "english")
            default_target_language = form.get("default_target_language")
            default_task_type = form.get("default_task_type", "text_translation")
            default_reward_amount = form.get("default_reward_amount")

            if not file or not hasattr(file, "read"):
                raise FormValidationError("Please select a JSONL file to upload")

            # Validate file extension
            if not file.filename or not file.filename.endswith((".jsonl", ".json")):
                raise FormValidationError(
                    "File must be a JSONL (.jsonl) or JSON (.json) file"
                )

            # Read and parse file content
            content = await file.read()
            content_str = content.decode("utf-8")

            # Parse JSONL content
            raw_data = []
            lines = content_str.strip().split("\n")

            for line_num, line in enumerate(lines, 1):
                if line.strip():  # Skip empty lines
                    try:
                        item_data = json.loads(line)
                        raw_data.append(item_data)
                    except json.JSONDecodeError as e:
                        raise FormValidationError(
                            f"Invalid JSON on line {line_num}: {str(e)}"
                        )

            if not raw_data:
                raise FormValidationError("No valid data found in file")

            # Build field mappings
            field_mappings = {"content_fields": content_fields}  # Now stores multiple fields
            if title_field:
                field_mappings["title_field"] = title_field
            if description_field:
                field_mappings["description_field"] = description_field
            if source_language_field:
                field_mappings["source_language_field"] = source_language_field
            if target_language_field:
                field_mappings["target_language_field"] = target_language_field
            if reward_amount_field:
                field_mappings["reward_amount_field"] = reward_amount_field

            # Build default values
            default_values = {}
            if default_source_language:
                default_values["source_language"] = default_source_language
            if default_target_language:
                default_values["target_language"] = default_target_language
            if default_task_type:
                default_values["task_type"] = default_task_type
            if default_reward_amount:
                default_values["reward_amount"] = Decimal(str(default_reward_amount))

            # Process flexible import
            success_count = 0
            error_count = 0
            errors = []
            created_task_ids = []
            sample_processed_data = []

            # Get admin user from session
            admin_user_id = request.session.get("admin_user_id")
            if not admin_user_id:
                raise FormValidationError("Admin user not found in session")

            with Session(engine) as session:
                for i, raw_item in enumerate(raw_data):
                    # Process each content field separately to create multiple tasks
                    for content_field_idx, content_field in enumerate(content_fields):
                        try:
                            # Extract fields using mappings
                            mapped_data = {}

                            # Required field: content
                            if content_field not in raw_item:
                                # Try nested field access (e.g., "translation.en")
                                content_value = raw_item
                                field_found = True
                                for key in content_field.split("."):
                                    if isinstance(content_value, dict) and key in content_value:
                                        content_value = content_value[key]
                                    else:
                                        field_found = False
                                        break
                                
                                if not field_found:
                                    raise ValueError(
                                        f"Required field '{content_field}' not found"
                                    )
                            else:
                                content_value = raw_item[content_field]

                            mapped_data["content"] = str(content_value)

                            # Optional fields with mappings
                            field_map = {
                                "title_field": "title",
                                "description_field": "description",
                                "source_language_field": "source_language",
                                "target_language_field": "target_language",
                                "reward_amount_field": "reward_amount",
                            }

                            for mapping_key, task_field in field_map.items():
                                if mapping_key in field_mappings:
                                    jsonl_key = field_mappings[mapping_key]
                                    if jsonl_key in raw_item:
                                        value = raw_item[jsonl_key]
                                        if (
                                            task_field == "reward_amount"
                                            and value is not None
                                        ):
                                            mapped_data[task_field] = Decimal(str(value))
                                        else:
                                            mapped_data[task_field] = (
                                                str(value) if value is not None else None
                                            )

                            # Apply default values for missing fields
                            for field, default_value in default_values.items():
                                if field not in mapped_data or mapped_data[field] is None:
                                    mapped_data[field] = default_value

                            # Set system defaults for required fields
                            if "title" not in mapped_data or not mapped_data["title"]:
                                # Include content field name in title for clarity
                                field_suffix = f" ({content_field})" if len(content_fields) > 1 else ""
                                mapped_data["title"] = f"Translation Task {i + 1}{field_suffix}"
                            if (
                                "task_type" not in mapped_data
                                or not mapped_data["task_type"]
                            ):
                                mapped_data["task_type"] = "text_translation"
                            if (
                                "source_language" not in mapped_data
                                or not mapped_data["source_language"]
                            ):
                                mapped_data["source_language"] = "unknown"
                            if (
                                "reward_amount" not in mapped_data
                                or mapped_data["reward_amount"] is None
                            ):
                                mapped_data["reward_amount"] = Decimal("0.00")

                            # Store sample for verification (first 3 items)
                            if len(sample_processed_data) < 3:
                                sample_processed_data.append(
                                    {"original": raw_item, "mapped": mapped_data, "content_field": content_field}
                                )

                            # Create TaskCreate object
                            task_create = TaskCreate(**mapped_data)

                            # Create and save task
                            task = Task.model_validate(
                                task_create, update={"created_by_id": admin_user_id}
                            )
                            session.add(task)
                            session.flush()  # Get the ID without committing

                            created_task_ids.append(str(task.id))
                            success_count += 1

                        except Exception as e:
                            error_count += 1
                            field_suffix = f" (field: {content_field})" if len(content_fields) > 1 else ""
                            errors.append(f"Row {i + 1}{field_suffix}: {str(e)}")

                # Commit all successful tasks
                if success_count > 0:
                    session.commit()

            # Prepare results
            total_rows = len(raw_data)
            total_possible_tasks = total_rows * len(content_fields)
            message = (
                f"Successfully imported {success_count} out of {total_possible_tasks} possible tasks "
                f"from {total_rows} rows with {len(content_fields)} content field(s)."
            )
            if error_count > 0:
                message += f" {error_count} tasks failed to import."

            import_results = {
                "success_count": success_count,
                "error_count": error_count,
                "total_count": total_possible_tasks,
                "total_rows": total_rows,
                "content_fields_count": len(content_fields),
                "content_fields": content_fields,
                "errors": errors[:10],  # Show only first 10 errors
                "created_task_ids": created_task_ids[:10],  # Show only first 10 IDs
                "message": message,
                "sample_processed_data": sample_processed_data,
            }

            return await self._render_form(
                request,
                templates,
                {
                    "success_message": message,
                    "import_results": import_results,
                },
            )

        except FormValidationError as e:
            return await self._render_form(request, templates, {"error_message": str(e)})
        except Exception as e:
            return await self._render_form(
                request, templates, {"error_message": f"Unexpected error: {str(e)}"}
            )
