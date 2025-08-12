import uuid
import json
from typing import Any
from decimal import Decimal
from datetime import datetime
from io import StringIO

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Task,
    TaskCreate,
    TaskPublic,
    TasksPublic,
    TaskUpdate,
    TaskSubmission,
    TaskSubmissionCreate,
    TaskSubmissionPublic,
    TaskSubmissionsPublic,
    TaskSubmissionUpdate,
    UserEarning,
    UserEarningCreate,
    UserEarningPublic,
    UserEarningsPublic,
    UserStats,
    Message,
    TaskType,
    Language,
    TaskStatus,
    SubmissionStatus,
    User,
    BulkTaskImportItem,
    BulkTaskImportRequest,
    BulkTaskImportResponse,
    FlexibleBulkImportRequest,
    FlexibleBulkImportResponse,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/", response_model=TasksPublic)
def read_tasks(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    task_type: str | None = None,
    language: str | None = None,
    status: str | None = None,
) -> Any:
    """
    Retrieve available tasks for users to work on.
    """
    # Build the query
    statement = select(Task)
    
    # Apply filters
    if task_type:
        statement = statement.where(Task.task_type == task_type)
    if language:
        statement = statement.where(Task.source_language == language)
    if status:
        statement = statement.where(Task.status == status)
    else:
        # By default, only show pending tasks for regular users
        if not current_user.is_superuser:
            statement = statement.where(Task.status == "pending")
    
    # Count total
    count_statement = select(func.count()).select_from(statement.subquery())
    count = session.exec(count_statement).one()
    
    # Get tasks with pagination
    statement = statement.offset(skip).limit(limit)
    tasks = session.exec(statement).all()
    
    # Add submission count for each task
    tasks_with_count = []
    for task in tasks:
        submission_count = session.exec(
            select(func.count()).select_from(TaskSubmission).where(TaskSubmission.task_id == task.id)
        ).one()
        task_dict = task.model_dump()
        task_dict["submission_count"] = submission_count
        tasks_with_count.append(TaskPublic(**task_dict))
    
    return TasksPublic(data=tasks_with_count, count=count)


@router.get("/{task_id}", response_model=TaskPublic)
def read_task(session: SessionDep, current_user: CurrentUser, task_id: uuid.UUID) -> Any:
    """
    Get task by ID.
    """
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get submission count
    submission_count = session.exec(
        select(func.count()).select_from(TaskSubmission).where(TaskSubmission.task_id == task.id)
    ).one()
    
    task_dict = task.model_dump()
    task_dict["submission_count"] = submission_count
    return TaskPublic(**task_dict)


@router.post("/", response_model=TaskPublic)
def create_task(
    *, session: SessionDep, current_user: CurrentUser, task_in: TaskCreate
) -> Any:
    """
    Create new task. Only superusers can create tasks.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    task = Task.model_validate(task_in, update={"created_by_id": current_user.id})
    session.add(task)
    session.commit()
    session.refresh(task)
    
    task_dict = task.model_dump()
    task_dict["submission_count"] = 0
    return TaskPublic(**task_dict)


@router.put("/{task_id}", response_model=TaskPublic)
def update_task(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    task_id: uuid.UUID,
    task_in: TaskUpdate,
) -> Any:
    """
    Update a task. Only superusers can update tasks.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    update_dict = task_in.model_dump(exclude_unset=True)
    update_dict["updated_at"] = datetime.utcnow()
    task.sqlmodel_update(update_dict)
    session.add(task)
    session.commit()
    session.refresh(task)
    
    # Get submission count
    submission_count = session.exec(
        select(func.count()).select_from(TaskSubmission).where(TaskSubmission.task_id == task.id)
    ).one()
    
    task_dict = task.model_dump()
    task_dict["submission_count"] = submission_count
    return TaskPublic(**task_dict)


@router.delete("/{task_id}")
def delete_task(
    session: SessionDep, current_user: CurrentUser, task_id: uuid.UUID
) -> Message:
    """
    Delete a task. Only superusers can delete tasks.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    session.delete(task)
    session.commit()
    return Message(message="Task deleted successfully")


# Task Submissions endpoints
@router.get("/{task_id}/submissions", response_model=TaskSubmissionsPublic)
def read_task_submissions(
    session: SessionDep,
    current_user: CurrentUser,
    task_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
) -> Any:
    """
    Get submissions for a specific task.
    """
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Build query
    statement = select(TaskSubmission).where(TaskSubmission.task_id == task_id)
    
    # Apply filters
    if status:
        statement = statement.where(TaskSubmission.status == status)
    
    # For regular users, only show their own submissions
    if not current_user.is_superuser:
        statement = statement.where(TaskSubmission.user_id == current_user.id)
    
    # Count total
    count_statement = select(func.count()).select_from(statement.subquery())
    count = session.exec(count_statement).one()
    
    # Get submissions with pagination
    statement = statement.offset(skip).limit(limit)
    submissions = session.exec(statement).all()
    
    return TaskSubmissionsPublic(data=submissions, count=count)


@router.post("/{task_id}/submissions", response_model=TaskSubmissionPublic)
def create_task_submission(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    task_id: uuid.UUID,
    submission_in: TaskSubmissionCreate,
) -> Any:
    """
    Submit work for a task.
    """
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status != "pending":
        raise HTTPException(status_code=400, detail="Task is not available for submissions")
    
    # Check if user already submitted for this task
    existing_submission = session.exec(
        select(TaskSubmission).where(
            TaskSubmission.task_id == task_id,
            TaskSubmission.user_id == current_user.id
        )
    ).first()
    
    if existing_submission:
        raise HTTPException(status_code=400, detail="You have already submitted for this task")
    
    # Check if max submissions reached
    submission_count = session.exec(
        select(func.count()).select_from(TaskSubmission).where(TaskSubmission.task_id == task_id)
    ).one()
    
    if submission_count >= task.max_submissions:
        raise HTTPException(status_code=400, detail="Maximum submissions reached for this task")
    
    # Validate submission based on task type
    if task.task_type == "text_translation":
        if not submission_in.content:
            raise HTTPException(status_code=400, detail="Translation content is required")
    elif task.task_type == "tts_recording":
        if not submission_in.audio_file_url:
            raise HTTPException(status_code=400, detail="Audio file URL is required")
    
    # Create submission
    submission = TaskSubmission.model_validate(
        submission_in,
        update={
            "task_id": task_id,
            "user_id": current_user.id,
        }
    )
    session.add(submission)
    session.commit()
    session.refresh(submission)
    
    return submission


@router.get("/submissions/{submission_id}", response_model=TaskSubmissionPublic)
def read_task_submission(
    session: SessionDep, current_user: CurrentUser, submission_id: uuid.UUID
) -> Any:
    """
    Get submission by ID.
    """
    submission = session.get(TaskSubmission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    # Check permissions
    if not current_user.is_superuser and submission.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    return submission


@router.put("/submissions/{submission_id}", response_model=TaskSubmissionPublic)
def update_task_submission(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    submission_id: uuid.UUID,
    submission_in: TaskSubmissionUpdate,
) -> Any:
    """
    Update a task submission. Users can update their own pending submissions,
    superusers can review and approve/reject submissions.
    """
    submission = session.get(TaskSubmission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    # Check permissions
    if not current_user.is_superuser and submission.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Users can only update their own pending submissions
    if not current_user.is_superuser:
        if submission.status != SubmissionStatus.PENDING:
            raise HTTPException(status_code=400, detail="Cannot update reviewed submission")
        # Users cannot change status or reviewer notes
        submission_in.status = None
        submission_in.reviewer_notes = None
    
    update_dict = submission_in.model_dump(exclude_unset=True)
    update_dict["updated_at"] = datetime.utcnow()
    
    # If superuser is approving/rejecting
    if current_user.is_superuser and submission_in.status:
        update_dict["reviewed_at"] = datetime.utcnow()
        update_dict["reviewer_id"] = current_user.id
        
        # If approving, create earnings record
        if submission_in.status == SubmissionStatus.APPROVED:
            task = session.get(Task, submission.task_id)
            if task and task.reward_amount > 0:
                # Create earning record
                earning = UserEarning(
                    user_id=submission.user_id,
                    submission_id=submission.id,
                    amount=task.reward_amount,
                    description=f"Reward for task: {task.title}"
                )
                session.add(earning)
                
                # Update user's total earnings
                user = session.get(User, submission.user_id)
                if user:
                    user.total_earnings += task.reward_amount
                    session.add(user)
    
    submission.sqlmodel_update(update_dict)
    session.add(submission)
    session.commit()
    session.refresh(submission)
    
    return submission


@router.delete("/submissions/{submission_id}")
def delete_task_submission(
    session: SessionDep, current_user: CurrentUser, submission_id: uuid.UUID
) -> Message:
    """
    Delete a task submission. Only users can delete their own pending submissions.
    """
    submission = session.get(TaskSubmission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    # Check permissions
    if submission.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Only allow deletion of pending submissions
    if submission.status != SubmissionStatus.PENDING:
        raise HTTPException(status_code=400, detail="Cannot delete reviewed submission")
    
    session.delete(submission)
    session.commit()
    return Message(message="Submission deleted successfully")


# User earnings and statistics
@router.get("/my-submissions", response_model=TaskSubmissionsPublic)
def read_my_submissions(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
) -> Any:
    """
    Get current user's task submissions.
    """
    statement = select(TaskSubmission).where(TaskSubmission.user_id == current_user.id)
    
    if status:
        statement = statement.where(TaskSubmission.status == status)
    
    # Count total
    count_statement = select(func.count()).select_from(statement.subquery())
    count = session.exec(count_statement).one()
    
    # Get submissions with pagination
    statement = statement.offset(skip).limit(limit).order_by(TaskSubmission.created_at.desc())
    submissions = session.exec(statement).all()
    
    return TaskSubmissionsPublic(data=submissions, count=count)


@router.get("/my-earnings", response_model=UserEarningsPublic)
def read_my_earnings(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Get current user's earnings.
    """
    statement = select(UserEarning).where(UserEarning.user_id == current_user.id)
    
    # Count total
    count_statement = select(func.count()).select_from(statement.subquery())
    count = session.exec(count_statement).one()
    
    # Get total earnings
    total_earnings_result = session.exec(
        select(func.sum(UserEarning.amount)).where(UserEarning.user_id == current_user.id)
    ).one()
    total_earnings = total_earnings_result or Decimal("0.00")
    
    # Get earnings with pagination
    statement = statement.offset(skip).limit(limit).order_by(UserEarning.created_at.desc())
    earnings = session.exec(statement).all()
    
    return UserEarningsPublic(data=earnings, count=count, total_earnings=total_earnings)


@router.get("/my-stats", response_model=UserStats)
def read_my_stats(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Get current user's task statistics.
    """
    # Total earnings
    total_earnings_result = session.exec(
        select(func.sum(UserEarning.amount)).where(UserEarning.user_id == current_user.id)
    ).one()
    total_earnings = total_earnings_result or Decimal("0.00")
    
    # Total submissions
    total_submissions = session.exec(
        select(func.count()).select_from(TaskSubmission).where(TaskSubmission.user_id == current_user.id)
    ).one()
    
    # Approved submissions
    approved_submissions = session.exec(
        select(func.count()).select_from(TaskSubmission).where(
            TaskSubmission.user_id == current_user.id,
            TaskSubmission.status == SubmissionStatus.APPROVED
        )
    ).one()
    
    # Pending submissions
    pending_submissions = session.exec(
        select(func.count()).select_from(TaskSubmission).where(
            TaskSubmission.user_id == current_user.id,
            TaskSubmission.status == SubmissionStatus.PENDING
        )
    ).one()
    
    # Rejected submissions
    rejected_submissions = session.exec(
        select(func.count()).select_from(TaskSubmission).where(
            TaskSubmission.user_id == current_user.id,
            TaskSubmission.status == SubmissionStatus.REJECTED
        )
    ).one()
    
    return UserStats(
        total_earnings=total_earnings,
        total_submissions=total_submissions,
        approved_submissions=approved_submissions,
        pending_submissions=pending_submissions,
        rejected_submissions=rejected_submissions,
    )


# Bulk Task Import Endpoints
@router.post("/bulk-import", response_model=BulkTaskImportResponse)
def bulk_import_tasks(
    *, session: SessionDep, current_user: CurrentUser, request: BulkTaskImportRequest
) -> Any:
    """
    Bulk import tasks from a list of task items. Only superusers can import tasks.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    success_count = 0
    error_count = 0
    errors = []
    created_task_ids = []
    
    for i, task_item in enumerate(request.tasks):
        try:
            # Apply defaults if not specified
            reward_amount = task_item.reward_amount
            if reward_amount == Decimal("0.00") and request.default_reward_amount:
                reward_amount = request.default_reward_amount
            
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
            task = Task.model_validate(task_create, update={"created_by_id": current_user.id})
            session.add(task)
            session.flush()  # Get the ID without committing
            
            created_task_ids.append(task.id)
            success_count += 1
            
        except Exception as e:
            error_count += 1
            errors.append(f"Row {i + 1}: {str(e)}")
    
    # Commit all successful tasks
    if success_count > 0:
        session.commit()
    
    total_count = len(request.tasks)
    message = f"Successfully imported {success_count} out of {total_count} tasks."
    if error_count > 0:
        message += f" {error_count} tasks failed to import."
    
    return BulkTaskImportResponse(
        success_count=success_count,
        error_count=error_count,
        total_count=total_count,
        errors=errors,
        created_task_ids=created_task_ids,
        message=message,
    )


@router.post("/bulk-import-jsonl", response_model=BulkTaskImportResponse)
async def bulk_import_tasks_from_jsonl(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile = File(...),
     default_reward_amount: Decimal | None = None,
) -> Any:
    """
    Bulk import tasks from a JSONL file. Only superusers can import tasks.
    Each line should be a JSON object with task fields.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Validate file type
    if not file.filename or not file.filename.endswith(('.jsonl', '.json')):
        raise HTTPException(
            status_code=400,
            detail="File must be a JSONL (.jsonl) or JSON (.json) file"
        )
    
    try:
        # Read file content
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
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid JSON on line {line_num}: {str(e)}"
                    )
                except Exception as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid task data on line {line_num}: {str(e)}"
                    )
        
        if not tasks:
            raise HTTPException(status_code=400, detail="No valid tasks found in file")
        
        # Create bulk import request
        bulk_request = BulkTaskImportRequest(
            tasks=tasks,
            default_reward_amount=default_reward_amount,
        )
        
        # Process the bulk import
        return bulk_import_tasks(
            session=session,
            current_user=current_user,
            request=bulk_request
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing file: {str(e)}"
        )


@router.post("/flexible-bulk-import", response_model=FlexibleBulkImportResponse)
def flexible_bulk_import_tasks(
    *, session: SessionDep, current_user: CurrentUser, request: FlexibleBulkImportRequest
) -> Any:
    """
    Flexible bulk import from any JSONL format with field mapping.
    Allows mapping any JSONL keys to task fields for maximum compatibility.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Validate required field mappings
    if "content_field" not in request.field_mappings:
        raise HTTPException(
            status_code=400,
            detail="content_field mapping is required"
        )
    
    success_count = 0
    error_count = 0
    errors = []
    created_task_ids = []
    sample_processed_data = []
    
    for i, raw_item in enumerate(request.raw_data):
        try:
            # Extract fields using mappings
            mapped_data = {}
            
            # Required field: content
            content_key = request.field_mappings["content_field"]
            if content_key not in raw_item:
                raise ValueError(f"Required field '{content_key}' not found")
            mapped_data["content"] = str(raw_item[content_key])
            
            # Optional fields with mappings
            field_map = {
                "title_field": "title",
                "description_field": "description", 
                "source_language_field": "source_language",
                "target_language_field": "target_language",
                "task_type_field": "task_type",
                "reward_amount_field": "reward_amount"
            }
            
            for mapping_key, task_field in field_map.items():
                if mapping_key in request.field_mappings:
                    jsonl_key = request.field_mappings[mapping_key]
                    if jsonl_key in raw_item:
                        value = raw_item[jsonl_key]
                        if task_field == "reward_amount" and value is not None:
                            mapped_data[task_field] = Decimal(str(value))
                        else:
                            mapped_data[task_field] = str(value) if value is not None else None
            
            # Apply default values for missing fields
            for field, default_value in request.default_values.items():
                if field not in mapped_data or mapped_data[field] is None:
                    if field == "reward_amount" and default_value is not None:
                        mapped_data[field] = Decimal(str(default_value))
                    else:
                        mapped_data[field] = default_value
            
            # Set system defaults for required fields
            if "title" not in mapped_data or not mapped_data["title"]:
                mapped_data["title"] = f"Translation Task {i + 1}"
            if "task_type" not in mapped_data or not mapped_data["task_type"]:
                mapped_data["task_type"] = "text_translation"
            if "source_language" not in mapped_data or not mapped_data["source_language"]:
                mapped_data["source_language"] = "unknown"
            if "reward_amount" not in mapped_data or mapped_data["reward_amount"] is None:
                mapped_data["reward_amount"] = Decimal("0.00")
            
            # Store sample for verification (first 3 items)
            if len(sample_processed_data) < 3:
                sample_processed_data.append({
                    "original": raw_item,
                    "mapped": mapped_data
                })
            
            # Create TaskCreate object
            task_create = TaskCreate(**mapped_data)
            
            # Create and save task
            task = Task.model_validate(task_create, update={"created_by_id": current_user.id})
            session.add(task)
            session.flush()  # Get the ID without committing
            
            created_task_ids.append(task.id)
            success_count += 1
            
        except Exception as e:
            error_count += 1
            errors.append(f"Row {i + 1}: {str(e)}")
    
    # Commit all successful tasks
    if success_count > 0:
        session.commit()
    
    total_count = len(request.raw_data)
    message = f"Successfully imported {success_count} out of {total_count} tasks."
    if error_count > 0:
        message += f" {error_count} tasks failed to import."
    
    return FlexibleBulkImportResponse(
        success_count=success_count,
        error_count=error_count,
        total_count=total_count,
        errors=errors[:10],  # Show only first 10 errors
        created_task_ids=created_task_ids[:10],  # Show only first 10 IDs
        message=message,
        sample_processed_data=sample_processed_data,
    )


@router.post("/flexible-bulk-import-jsonl", response_model=FlexibleBulkImportResponse)
async def flexible_bulk_import_from_jsonl(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile = File(...),
    content_field: str,
    title_field: str | None = None,
    description_field: str | None = None,
    source_language_field: str | None = None,
    target_language_field: str | None = None,
    task_type_field: str | None = None,
    reward_amount_field: str | None = None,
    default_title: str | None = None,
    default_description: str | None = None,
    default_source_language: str = "unknown",
    default_target_language: str | None = None,
    default_task_type: str = "text_translation",
    default_reward_amount: Decimal | None = None,
) -> Any:
    """
    Flexible bulk import from JSONL file with custom field mapping.
    Perfect for Hugging Face datasets and other JSONL formats.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Validate file type
    if not file.filename or not file.filename.endswith(('.jsonl', '.json')):
        raise HTTPException(
            status_code=400,
            detail="File must be a JSONL (.jsonl) or JSON (.json) file"
        )
    
    try:
        # Read file content
        content = await file.read()
        content_str = content.decode('utf-8')
        
        # Parse JSONL content
        raw_data = []
        lines = content_str.strip().split('\n')
        
        for line_num, line in enumerate(lines, 1):
            if line.strip():  # Skip empty lines
                try:
                    item_data = json.loads(line)
                    raw_data.append(item_data)
                except json.JSONDecodeError as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid JSON on line {line_num}: {str(e)}"
                    )
        
        if not raw_data:
            raise HTTPException(status_code=400, detail="No valid data found in file")
        
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
        if task_type_field:
            field_mappings["task_type_field"] = task_type_field
        if reward_amount_field:
            field_mappings["reward_amount_field"] = reward_amount_field
        
        # Build default values
        default_values = {}
        if default_title:
            default_values["title"] = default_title
        if default_description:
            default_values["description"] = default_description
        if default_source_language:
            default_values["source_language"] = default_source_language
        if default_target_language:
            default_values["target_language"] = default_target_language
        if default_task_type:
            default_values["task_type"] = default_task_type
        if default_reward_amount is not None:
            default_values["reward_amount"] = default_reward_amount
        
        # Create flexible import request
        flexible_request = FlexibleBulkImportRequest(
            field_mappings=field_mappings,
            default_values=default_values,
            raw_data=raw_data,
        )
        
        # Process the flexible import
        return flexible_bulk_import_tasks(
            session=session,
            current_user=current_user,
            request=flexible_request
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing file: {str(e)}"
        )