from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.core.database import get_db
from app.models.user import User
from app.services.auth import get_current_user
from app.services.education import EducationService

router = APIRouter(prefix="/education", tags=["教务系统"])


class CaptchaResponse(BaseModel):
    session_id: str
    captcha_image: str


class LoginRequest(BaseModel):
    student_id: str
    password: str
    captcha: str
    session_id: str


class EducationLoginResponse(BaseModel):
    success: bool
    message: str
    student_name: Optional[str] = None


class GradeResponse(BaseModel):
    course_name: str
    credit: float
    grade: str
    semester: str
    academic_year: str


class ScheduleResponse(BaseModel):
    course_name: str
    teacher: Optional[str]
    location: Optional[str]
    day_of_week: int
    start_time: str
    end_time: str
    weeks: str


@router.get("/captcha", response_model=CaptchaResponse)
async def get_captcha():
    service = EducationService()
    session_id, captcha_image = await service.get_captcha()
    return CaptchaResponse(session_id=session_id, captcha_image=captcha_image)


@router.post("/login", response_model=EducationLoginResponse)
async def login_education(
    data: LoginRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = EducationService()
    result = await service.login(
        student_id=data.student_id,
        password=data.password,
        captcha=data.captcha,
        session_id=data.session_id,
    )
    
    if result["success"]:
        current_user.education_password = data.password
        await db.commit()
    
    return EducationLoginResponse(**result)


@router.get("/grades", response_model=list[GradeResponse])
async def get_grades(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not current_user.education_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先登录教务系统")
    
    service = EducationService()
    grades = await service.fetch_grades(
        student_id=current_user.student_id,
        password=current_user.education_password,
    )
    return grades


@router.get("/schedule", response_model=list[ScheduleResponse])
async def get_schedule(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not current_user.education_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先登录教务系统")
    
    service = EducationService()
    schedule = await service.fetch_schedule(
        student_id=current_user.student_id,
        password=current_user.education_password,
    )
    return schedule
