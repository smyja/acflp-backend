import uuid
from typing import Any
from decimal import Decimal
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
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