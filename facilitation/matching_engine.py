"""
Matching Engine for Pedne Sewa Trust - Employment Facilitation Platform.
Evaluates candidates against Government and Private job opportunities using
a tiered hard/soft criteria model, identifies document blockers, and enforces
the mandatory disclaimer: 'Potential Match — Verify Eligibility Against Official Advertisement'.
"""

import re
from typing import List, Dict, Any, Optional
from models.candidate import Candidate
from models.facilitation import GovernmentJob, PrivateJob, CandidateDocument, JobMatchResult
from facilitation.document_manager import document_manager

DISCLAIMER_TEXT = "Potential Match — Verify Eligibility Against Official Advertisement"

QUALIFICATION_HIERARCHY = {
    "below 10th": 1,
    "8th": 1,
    "9th": 1,
    "10th": 2,
    "10th / ssc": 2,
    "ssc": 2,
    "12th": 3,
    "12th / hssc": 3,
    "hssc": 3,
    "iti": 3,
    "diploma": 4,
    "polytechnic": 4,
    "graduate": 5,
    "graduate / bachelor's": 5,
    "bachelor": 5,
    "b.a": 5,
    "b.sc": 5,
    "b.com": 5,
    "b.e": 5,
    "b.tech": 5,
    "mbbs": 5,
    "post graduate": 6,
    "post graduate / master's": 6,
    "master": 6,
    "m.a": 6,
    "m.sc": 6,
    "m.com": 6,
    "m.e": 6,
    "m.tech": 6,
    "doctorate": 7,
    "ph.d": 7
}


def _get_qualification_rank(qual_str: str) -> int:
    """Returns numerical rank for qualification comparison."""
    if not qual_str:
        return 0
    q = qual_str.strip().lower()
    for k, rank in QUALIFICATION_HIERARCHY.items():
        if k in q:
            return rank
    return 2  # default baseline if unknown text


class MatchingEngine:
    """Core facilitation matching algorithm."""

    @staticmethod
    def match_candidate_to_government_job(
        candidate: Candidate,
        job: GovernmentJob,
        documents: List[CandidateDocument]
    ) -> JobMatchResult:
        """
        Matches a candidate against a Government opportunity.
        Evaluates qualification, age, experience, and document prerequisites.
        """
        matched_criteria = []
        missing_criteria = []
        document_gaps = []
        score = 0.0

        # Check critical candidate data
        if not candidate.education.highest_qualification and candidate.age is None:
            return JobMatchResult(
                job_id=job.job_id,
                candidate_id=candidate.candidate_id,
                job_title=job.post_name,
                organization=job.department,
                job_type="Government",
                match_tier="NOT ENOUGH INFORMATION",
                score=0.0,
                matched_criteria=[],
                missing_criteria=["Candidate educational qualification and age are not recorded."],
                document_gaps=[],
                disclaimer=DISCLAIMER_TEXT
            )

        # 1. Hard requirement: Qualification level
        cand_rank = _get_qualification_rank(candidate.education.highest_qualification or candidate.education.degree_course)
        job_rank = _get_qualification_rank(job.minimum_qualification)

        qual_pass = False
        if job_rank == 0 or cand_rank >= job_rank:
            qual_pass = True
            matched_criteria.append(f"✓ Qualification: Meets or exceeds minimum requirement ({job.minimum_qualification or 'Any'})")
            score += 35.0
        else:
            missing_criteria.append(
                f"⚠ Qualification gap: Requires {job.minimum_qualification}, candidate profile shows {candidate.education.highest_qualification or 'None'}"
            )

        # 2. Hard requirement: Age limits
        age_pass = True
        if candidate.age is not None:
            if candidate.age < job.age_limit_min:
                age_pass = False
                missing_criteria.append(f"⚠ Age: Candidate is {candidate.age} yrs (minimum age is {job.age_limit_min})")
            elif candidate.age > job.age_limit_max:
                age_pass = False
                missing_criteria.append(f"⚠ Age: Candidate is {candidate.age} yrs (maximum age limit is {job.age_limit_max})")
            else:
                matched_criteria.append(f"✓ Age: Within allowed range ({job.age_limit_min} - {job.age_limit_max} years)")
                score += 25.0
        else:
            missing_criteria.append("⚠ Age: Not specified on candidate record")

        # 3. Experience requirements (Hard/Soft)
        cand_exp = candidate.employment.years_experience or candidate.preferences.total_experience_years or 0.0
        if job.experience_requirement_years <= 0.0:
            matched_criteria.append("✓ Experience: Freshers eligible / No prior experience required")
            score += 15.0
        elif cand_exp >= job.experience_requirement_years:
            matched_criteria.append(f"✓ Experience: Candidate has {cand_exp:.1f} yrs (required {job.experience_requirement_years:.1f} yrs)")
            score += 15.0
        else:
            missing_criteria.append(
                f"⚠ Experience: Job requires {job.experience_requirement_years:.1f} yrs, candidate profile has {cand_exp:.1f} yrs"
            )

        # 4. Document readiness blockers
        if job.required_documents:
            doc_eval = document_manager.check_job_document_eligibility(documents, job.required_documents)
            for m in doc_eval["matched_documents"]:
                matched_criteria.append(f"✓ Document: {m} is available")
            for g in doc_eval["document_gaps"]:
                document_gaps.append(f"⚠ {g}")

            if doc_eval["has_all_documents"]:
                score += 25.0
            else:
                # Partial document credit
                partial_ratio = len(doc_eval["matched_documents"]) / len(job.required_documents)
                score += (25.0 * partial_ratio)
        else:
            score += 25.0

        # Determine Match Tier
        score = min(100.0, round(score, 1))
        if qual_pass and age_pass and not document_gaps and score >= 75.0:
            tier = "HIGH MATCH"
        elif qual_pass and (not document_gaps or score >= 45.0):
            tier = "MEDIUM MATCH"
        else:
            tier = "LOW MATCH"

        return JobMatchResult(
            job_id=job.job_id,
            candidate_id=candidate.candidate_id,
            job_title=job.post_name,
            organization=job.department,
            job_type="Government",
            match_tier=tier,
            score=score,
            matched_criteria=matched_criteria,
            missing_criteria=missing_criteria,
            document_gaps=document_gaps,
            disclaimer=DISCLAIMER_TEXT
        )

    @staticmethod
    def match_candidate_to_private_job(
        candidate: Candidate,
        job: PrivateJob,
        documents: List[CandidateDocument]
    ) -> JobMatchResult:
        """
        Matches a candidate against a Private opportunity.
        Evaluates qualification, experience, skills match, location, and documents.
        """
        matched_criteria = []
        missing_criteria = []
        document_gaps = []
        score = 0.0

        # 1. Qualification match
        cand_rank = _get_qualification_rank(candidate.education.highest_qualification or candidate.education.degree_course)
        job_rank = _get_qualification_rank(job.required_qualification)

        if job_rank == 0 or cand_rank >= job_rank:
            matched_criteria.append(f"✓ Qualification: Meets required level ({job.required_qualification or 'Any'})")
            score += 25.0
        else:
            missing_criteria.append(
                f"⚠ Qualification: Requires {job.required_qualification}, candidate profile has {candidate.education.highest_qualification or 'None'}"
            )

        # 2. Experience match
        cand_exp = candidate.employment.years_experience or candidate.preferences.total_experience_years or 0.0
        if job.required_experience_years <= 0.0:
            matched_criteria.append("✓ Experience: Freshers welcome")
            score += 20.0
        elif cand_exp >= job.required_experience_years:
            matched_criteria.append(f"✓ Experience: {cand_exp:.1f} yrs matches requirement ({job.required_experience_years:.1f} yrs)")
            score += 20.0
        else:
            missing_criteria.append(
                f"⚠ Experience: Job requires {job.required_experience_years:.1f} yrs, candidate has {cand_exp:.1f} yrs"
            )

        # 3. Skills overlap
        cand_skills = set(re.findall(r"\w+", (candidate.education.skills + " " + candidate.preferences.skills_list).lower()))
        job_skills = set(re.findall(r"\w+", (job.required_skills or "").lower()))

        # Remove common stop words
        stop_words = {"and", "or", "in", "to", "for", "with", "a", "an", "the", "of", "on"}
        cand_skills -= stop_words
        job_skills -= stop_words

        if job_skills:
            common = cand_skills.intersection(job_skills)
            if common:
                matched_criteria.append(f"✓ Skills overlap: {', '.join(sorted(list(common))[:4])}")
                overlap_ratio = len(common) / len(job_skills)
                score += min(25.0, round(25.0 * overlap_ratio * 1.5, 1))
            else:
                missing_criteria.append(f"⚠ Required skills: {job.required_skills}")
        else:
            score += 20.0

        # 4. Location match & Preferences
        cand_loc = (candidate.village or "").lower()
        pref_loc = (candidate.preferences.preferred_location or "").lower()
        job_loc = (job.location or "").lower()

        if "pernem" in job_loc or cand_loc in job_loc or pref_loc in job_loc or candidate.preferences.willing_to_relocate:
            matched_criteria.append(f"✓ Location: Convenient location ({job.location})")
            score += 15.0
        else:
            missing_criteria.append(f"⚠ Location: Job is in {job.location}, candidate is in {candidate.village}")

        # 5. Document readiness
        if job.required_documents:
            doc_eval = document_manager.check_job_document_eligibility(documents, job.required_documents)
            for m in doc_eval["matched_documents"]:
                matched_criteria.append(f"✓ Document: {m} is available")
            for g in doc_eval["document_gaps"]:
                document_gaps.append(f"⚠ {g}")
            if doc_eval["has_all_documents"]:
                score += 15.0
            else:
                partial_ratio = len(doc_eval["matched_documents"]) / len(job.required_documents)
                score += (15.0 * partial_ratio)
        else:
            doc_map = {d.document_type: d for d in documents if d.status == "Available"}
            if "Resume / Biodata" in doc_map or "10th / SSC Marksheet & Certificate" in doc_map:
                matched_criteria.append("✓ Documents: Key candidate profile documents available")
                score += 15.0
            else:
                document_gaps.append("⚠ Missing Resume / Biodata or Identity Document")

        # Determine Tier
        score = min(100.0, round(score, 1))
        if score >= 75.0:
            tier = "HIGH MATCH"
        elif score >= 45.0:
            tier = "MEDIUM MATCH"
        else:
            tier = "LOW MATCH"

        return JobMatchResult(
            job_id=job.job_id,
            candidate_id=candidate.candidate_id,
            job_title=job.job_title,
            organization=job.employer,
            job_type="Private",
            match_tier=tier,
            score=score,
            matched_criteria=matched_criteria,
            missing_criteria=missing_criteria,
            document_gaps=document_gaps,
            disclaimer=DISCLAIMER_TEXT
        )


matching_engine = MatchingEngine()
