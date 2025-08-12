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
from app.models import Task, BulkTaskImportItem, TaskCreate, FlexibleBulkImportRequest


class FlexibleBulkImportView(CustomView):
    """Custom admin view for flexible JSONL import with field mapping"""

    def __init__(self):
        super().__init__(
            label="Flexible JSONL Import",
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

            # Required field mapping
            content_field = form.get("content_field")
            if not content_field:
                raise FormValidationError("Content field mapping is required")

            # Optional field mappings
            title_field = form.get("title_field")
            description_field = form.get("description_field")
            source_language_field = form.get("source_language_field")
            target_language_field = form.get("target_language_field")
            reward_amount_field = form.get("reward_amount_field")

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
            field_mappings = {"content_field": content_field}
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
                    try:
                        # Extract fields using mappings
                        mapped_data = {}

                        # Required field: content
                        if content_field not in raw_item:
                            raise ValueError(
                                f"Required field '{content_field}' not found"
                            )

                        # Handle nested field access (e.g., "translation.en")
                        content_value = raw_item
                        for key in content_field.split("."):
                            if isinstance(content_value, dict) and key in content_value:
                                content_value = content_value[key]
                            else:
                                raise ValueError(
                                    f"Field path '{content_field}' not found"
                                )

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
                            mapped_data["title"] = f"Translation Task {i + 1}"
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
                                {"original": raw_item, "mapped": mapped_data}
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
                        errors.append(f"Row {i + 1}: {str(e)}")

                # Commit all successful tasks
                if success_count > 0:
                    session.commit()

            # Prepare results
            total_count = len(raw_data)
            message = (
                f"Successfully imported {success_count} out of {total_count} tasks."
            )
            if error_count > 0:
                message += f" {error_count} tasks failed to import."

            import_results = {
                "success_count": success_count,
                "error_count": error_count,
                "total_count": total_count,
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




class BulkTaskImportView(CustomView):
    """Custom admin view for bulk task import from JSONL files"""

    def __init__(self):
        super().__init__(
            label="Bulk Task Import",
            icon="fa fa-upload",
            path="/bulk-task-import",
            template_path="bulk_import.html",
            name="bulk-task-import",
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
        """Render the bulk import form"""
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
        """Handle JSONL file upload and process bulk import"""
        try:
            form = await request.form()
            file = form.get("jsonl_file")
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
            tasks = []
            lines = content_str.strip().split("\n")

            for line_num, line in enumerate(lines, 1):
                if line.strip():  # Skip empty lines
                    try:
                        task_data = json.loads(line)
                        task_item = BulkTaskImportItem(**task_data)
                        tasks.append(task_item)
                    except json.JSONDecodeError as e:
                        raise FormValidationError(
                            f"Invalid JSON on line {line_num}: {str(e)}"
                        )
                    except Exception as e:
                        raise FormValidationError(
                            f"Invalid task data on line {line_num}: {str(e)}"
                        )

            if not tasks:
                raise FormValidationError("No valid tasks found in file")

            # Process bulk import
            success_count = 0
            error_count = 0
            errors = []
            created_task_ids = []

            # Get admin user from session (assuming it's stored there)
            admin_user_id = request.session.get("admin_user_id")
            if not admin_user_id:
                raise FormValidationError("Admin user not found in session")

            with Session(engine) as session:
                for i, task_item in enumerate(tasks):
                    try:
                        # Apply defaults if not specified
                        reward_amount = task_item.reward_amount
                        if reward_amount == Decimal("0.00") and default_reward_amount:
                            reward_amount = Decimal(str(default_reward_amount))

                        # Create TaskCreate object
                        task_create = TaskCreate(
                            title=task_item.title,
                            description=task_item.description,
                            task_type=task_item.task_type,
                            source_language=task_item.source_language,
                            target_language=task_item.target_language,
                            content=task_item.content,
                            reward_amount=reward_amount,
                        )

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
                        errors.append(f"Row {i + 1}: {str(e)}")

                # Commit all successful tasks
                if success_count > 0:
                    session.commit()

            # Prepare results
            total_count = len(tasks)
            message = (
                f"Successfully imported {success_count} out of {total_count} tasks."
            )
            if error_count > 0:
                message += f" {error_count} tasks failed to import."

            import_results = {
                "success_count": success_count,
                "error_count": error_count,
                "total_count": total_count,
                "errors": errors[:10],  # Show only first 10 errors
                "created_task_ids": created_task_ids[:10],  # Show only first 10 IDs
                "message": message,
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
