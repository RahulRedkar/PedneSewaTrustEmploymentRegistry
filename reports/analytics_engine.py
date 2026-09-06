"""
Analytics & Aggregation Engine for Pedne Sewa Trust - Employment Registry.
Computes demographic, geographic, and employment statistics across candidate records.
"""

from typing import List, Dict, Any, Optional
from collections import Counter, defaultdict
from database.repository import repository
from models.candidate import Candidate
from app.constants import (
    PERNEM_VILLAGES,
    QUALIFICATION_LEVELS,
    STATUS_EMPLOYED,
    STATUS_UNEMPLOYED,
    STATUS_SELF_EMPLOYED,
    STATUS_STUDENT,
    EXPERIENCE_RANGES,
    GOVT_RESULT_STATUSES
)


class AnalyticsEngine:
    """Computes demographic, employment, and skills analytics."""

    def filter_candidates(
        self,
        candidates: List[Candidate],
        village: Optional[str] = None,
        status: Optional[str] = None,
        qualification: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        min_age: Optional[int] = None,
        max_age: Optional[int] = None,
        sector: Optional[str] = None
    ) -> List[Candidate]:
        """Applies multi-dimensional filters to a candidate list."""
        filtered = []
        for c in candidates:
            if village and village != "All" and c.village != village:
                continue
            if status and status != "All" and c.employment.status != status:
                continue
            if qualification and qualification != "All" and c.education.highest_qualification != qualification:
                continue
            if start_date and c.created_at[:10] < start_date:
                continue
            if end_date and c.created_at[:10] > end_date:
                continue
            if min_age is not None and (c.age is None or c.age < min_age):
                continue
            if max_age is not None and (c.age is None or c.age > max_age):
                continue
            if sector and sector != "All" and c.preferences.preferred_sector != sector:
                continue
            filtered.append(c)
        return filtered

    def get_dashboard_summary(self, candidates: Optional[List[Candidate]] = None) -> Dict[str, Any]:
        """Computes top-level KPI metrics for the Dashboard."""
        if candidates is None:
            candidates = repository.get_all_candidates(include_deleted=False)

        total = len(candidates)
        employed = sum(1 for c in candidates if c.employment.status == STATUS_EMPLOYED)
        unemployed = sum(1 for c in candidates if c.employment.status == STATUS_UNEMPLOYED)
        self_employed = sum(1 for c in candidates if c.employment.status == STATUS_SELF_EMPLOYED)
        students = sum(1 for c in candidates if c.employment.status == STATUS_STUDENT)

        govt_employed = sum(1 for c in candidates if c.employment.status == STATUS_EMPLOYED and c.employment.category == "Government")
        # Ensure Employed exactly reconciles: Employed = Govt Employed + Private Employed
        private_employed = max(0, employed - govt_employed)

        govt_applicants = sum(1 for c in candidates if c.employment.status == STATUS_UNEMPLOYED and c.employment.govt_applied)
        # Ensure Unemployed exactly reconciles: Unemployed = Govt Applicants + Never Applied
        never_applied = max(0, unemployed - govt_applicants)

        emp_rate = (employed / total * 100) if total > 0 else 0.0

        return {
            "total_candidates": total,
            "employed": employed,
            "unemployed": unemployed,
            "self_employed": self_employed,
            "students": students,
            "govt_employed": govt_employed,
            "private_employed": private_employed,
            "govt_applicants": govt_applicants,
            "never_applied": never_applied,
            "employment_rate": round(emp_rate, 1)
        }

    def generate_employment_report(self, candidates: List[Candidate]) -> Dict[str, Any]:
        """Generates detailed employment breakdown report."""
        summary = self.get_dashboard_summary(candidates)
        return {
            "title": "Overall Employment Summary Report",
            "metrics": summary,
            "rows": [
                ("Total Registered Candidates", summary["total_candidates"], "100.0%"),
                ("Employed — Government", summary["govt_employed"], f"{summary['govt_employed']/max(1, summary['total_candidates'])*100:.1f}%"),
                ("Employed — Private", summary["private_employed"], f"{summary['private_employed']/max(1, summary['total_candidates'])*100:.1f}%"),
                ("Self-Employed / Entrepreneurs", summary["self_employed"], f"{summary['self_employed']/max(1, summary['total_candidates'])*100:.1f}%"),
                ("Students / Trainees", summary["students"], f"{summary['students']/max(1, summary['total_candidates'])*100:.1f}%"),
                ("Unemployed — Govt Applicants", summary["govt_applicants"], f"{summary['govt_applicants']/max(1, summary['total_candidates'])*100:.1f}%"),
                ("Unemployed — Never Applied", summary["never_applied"], f"{summary['never_applied']/max(1, summary['total_candidates'])*100:.1f}%"),
            ]
        }

    def generate_village_report(self, candidates: List[Candidate]) -> List[Dict[str, Any]]:
        """Generates village-by-village breakdown of employment status."""
        village_data = defaultdict(lambda: {
            "total": 0, "employed": 0, "unemployed": 0,
            "govt": 0, "private": 0, "self_emp": 0, "student": 0
        })

        for c in candidates:
            v = c.village or "Unknown"
            s = c.employment.status
            cat = c.employment.category

            village_data[v]["total"] += 1
            if s == STATUS_EMPLOYED:
                village_data[v]["employed"] += 1
                if cat == "Government":
                    village_data[v]["govt"] += 1
                elif cat == "Private":
                    village_data[v]["private"] += 1
            elif s == STATUS_UNEMPLOYED:
                village_data[v]["unemployed"] += 1
            elif s == STATUS_SELF_EMPLOYED:
                village_data[v]["self_emp"] += 1
            elif s == STATUS_STUDENT:
                village_data[v]["student"] += 1

        rows = []
        for v in sorted(village_data.keys()):
            d = village_data[v]
            emp_pct = (d["employed"] / d["total"] * 100) if d["total"] > 0 else 0
            rows.append({
                "village": v,
                "total": d["total"],
                "employed": d["employed"],
                "unemployed": d["unemployed"],
                "govt_employed": d["govt"],
                "private_employed": d["private"],
                "self_employed": d["self_emp"],
                "students": d["student"],
                "employment_rate": f"{emp_pct:.1f}%"
            })
        return rows

    def generate_qualification_report(self, candidates: List[Candidate]) -> List[Dict[str, Any]]:
        """Groups candidates by highest qualification level."""
        counts = Counter(c.education.highest_qualification or "Unspecified" for c in candidates)
        total = max(1, len(candidates))
        rows = []
        for qual, count in counts.most_common():
            rows.append({
                "qualification": qual,
                "count": count,
                "percentage": f"{(count / total * 100):.1f}%"
            })
        return rows

    def generate_experience_report(self, candidates: List[Candidate]) -> List[Dict[str, Any]]:
        """Groups candidates into standardized experience bands."""
        bands = {b: 0 for b in EXPERIENCE_RANGES}
        for c in candidates:
            years = c.employment.years_experience or c.preferences.total_experience_years or 0.0
            if years == 0:
                bands["0 years (Fresher)"] += 1
            elif years < 1.0:
                bands["Less than 1 year"] += 1
            elif 1.0 <= years < 3.0:
                bands["1–3 years"] += 1
            elif 3.0 <= years < 5.0:
                bands["3–5 years"] += 1
            elif 5.0 <= years < 10.0:
                bands["5–10 years"] += 1
            else:
                bands["10+ years"] += 1

        total = max(1, len(candidates))
        return [
            {"experience_range": band, "count": count, "percentage": f"{(count / total * 100):.1f}%"}
            for band, count in bands.items()
        ]

    def generate_govt_employment_report(self, candidates: List[Candidate]) -> Dict[str, Any]:
        """Analyzes government employees and examination aspirants."""
        govt_employed = [c for c in candidates if c.employment.status == STATUS_EMPLOYED and c.employment.category == "Government"]
        govt_applicants = [c for c in candidates if c.employment.status == STATUS_UNEMPLOYED and c.employment.govt_applied]
        never_applied = [c for c in candidates if c.employment.status == STATUS_UNEMPLOYED and not c.employment.govt_applied]

        status_counts = Counter(c.employment.govt_result_status or "Awaiting Result" for c in govt_applicants)

        return {
            "govt_employed_count": len(govt_employed),
            "govt_applicants_count": len(govt_applicants),
            "never_applied_count": len(never_applied),
            "result_status_breakdown": [
                {"status": s, "count": status_counts.get(s, 0)} for s in GOVT_RESULT_STATUSES
            ]
        }

    def generate_job_preference_and_skills_report(self, candidates: List[Candidate]) -> Dict[str, Any]:
        """Identifies top requested job sectors, roles, locations, and top skills."""
        sectors = Counter(c.preferences.preferred_sector for c in candidates if c.preferences.preferred_sector)
        roles = Counter(c.preferences.preferred_role for c in candidates if c.preferences.preferred_role)
        locations = Counter(c.preferences.preferred_location for c in candidates if c.preferences.preferred_location)

        skills = []
        for c in candidates:
            combined = f"{c.education.skills}, {c.preferences.skills_list}"
            for item in combined.split(","):
                clean = item.strip()
                if clean:
                    skills.append(clean.title())
        skills_counter = Counter(skills)

        return {
            "top_sectors": sectors.most_common(10),
            "top_roles": roles.most_common(10),
            "top_locations": locations.most_common(10),
            "top_skills": skills_counter.most_common(15)
        }


analytics_engine = AnalyticsEngine()
