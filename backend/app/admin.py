from typing import Any
from decimal import Decimal
import json
from io import StringIO

from starlette.requests import Request
from starlette.responses import Response, RedirectResponse
from starlette_admin.views import BaseView
from starlette_admin.exceptions import FormValidationError
from sqlmodel import Session

from app.core.db import engine
from app.models import Task, BulkTaskImportItem, TaskCreate, FlexibleBulkImportRequest


class BulkTaskImportView(BaseView):
    """Custom admin view for bulk task import from JSONL files"""
    
    def __init__(self):
        super().__init__()
        self.name = "Bulk Task Import"
        self.icon = "fa fa-upload"
        self.template = "bulk_import.html"


class FlexibleBulkImportView(BaseView):
    """Custom admin view for flexible JSONL import with field mapping"""
    
    def __init__(self):
        super().__init__()
        self.name = "Flexible JSONL Import"
        self.icon = "fa fa-magic"
        self.template = "flexible_import.html"
    
    def is_accessible(self, request: Request) -> bool:
        """Only allow access to authenticated admin users"""
        return request.session.get("admin_user") is not None
    
    async def render(self, request: Request, params: dict[str, Any]) -> Response:
        """Render the bulk import form"""
        context = {
            "request": request,
            "view": self,
            "success_message": params.get("success_message"),
            "error_message": params.get("error_message"),
            "import_results": params.get("import_results"),
        }
        return self.templates.TemplateResponse(self.template, context)
    
    async def handle_upload(self, request: Request) -> Response:
        """Handle JSONL file upload and process bulk import"""
        try:
            form = await request.form()
            file = form.get("jsonl_file")
            default_reward_amount = form.get("default_reward_amount")
            
            if not file or not hasattr(file, 'read'):
                raise FormValidationError("Please select a JSONL file to upload")
            
            # Validate file extension
            if not file.filename or not file.filename.endswith(('.jsonl', '.json')):
                raise FormValidationError("File must be a JSONL (.jsonl) or JSON (.json) file")
            
            # Read and parse file content
            content = await file.read()
            content_str = content.decode('utf-8')
            
            # Parse JSONL content
            tasks = []
            lines = content_str.strip().split('\n')
            
            for line_num, line in enumerate(lines, 1):
                if line.strip():  # Skip empty lines
                    try:
                        task_data = json.loads(line)
                        task_item = BulkTaskImportItem(**task_data)
                        tasks.append(task_item)
                    except json.JSONDecodeError as e:
                        raise FormValidationError(f"Invalid JSON on line {line_num}: {str(e)}")
                    except Exception as e:
                        raise FormValidationError(f"Invalid task data on line {line_num}: {str(e)}")
            
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
                        task = Task.model_validate(task_create, update={"created_by_id": admin_user_id})
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
            message = f"Successfully imported {success_count} out of {total_count} tasks."
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
            
            return await self.render(request, {
                "success_message": message,
                "import_results": import_results,
            })
            
        except FormValidationError as e:
            return await self.render(request, {"error_message": str(e)})
        except Exception as e:
            return await self.render(request, {"error_message": f"Unexpected error: {str(e)}"})
    
    async def dispatch(self, request: Request) -> Response:
        """Handle different HTTP methods"""
        if request.method == "GET":
            return await self.render(request, {})
        elif request.method == "POST":
            return await self.handle_upload(request)
        else:
            return Response("Method not allowed", status_code=405)