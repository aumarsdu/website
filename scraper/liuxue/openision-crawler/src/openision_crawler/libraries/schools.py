from __future__ import annotations

from collections import defaultdict

from openision_crawler.libraries.models import AdmissionCase, Program, School


def _gpa_distribution(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "min": None, "max": None, "avg": None}
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "avg": round(sum(values) / len(values), 2),
    }


def build_schools(programs: list[Program], cases: list[AdmissionCase]) -> list[School]:
    programs_by_school: dict[str, list[Program]] = defaultdict(list)
    cases_by_school: dict[str, list[AdmissionCase]] = defaultdict(list)

    for program in programs:
        programs_by_school[program.school_id].append(program)
    for case in cases:
        cases_by_school[case.target_school_id].append(case)

    schools: list[School] = []
    for school_id in sorted(set(programs_by_school) | set(cases_by_school)):
        school_programs = sorted(programs_by_school.get(school_id, []), key=lambda item: item.program_id)
        school_cases = cases_by_school.get(school_id, [])
        first = school_programs[0] if school_programs else None
        directions = sorted({item.major_direction for item in school_programs if item.major_direction})
        years = [item.admission_year for item in school_cases if item.admission_year_valid and item.admission_year]
        gpas = [item.china_gpa for item in school_cases if item.china_gpa is not None]
        schools.append(
            School(
                school_id=school_id,
                school_name_cn=first.school_name_cn if first else None,
                school_name_en=first.school_name_en if first else None,
                country=first.country if first else None,
                qs_rank=first.qs_rank if first else None,
                program_count=len(school_programs),
                case_count=len(school_cases),
                major_directions=directions,
                top_programs=[
                    {"program_id": item.program_id, "major_name_cn": item.major_name_cn}
                    for item in school_programs[:10]
                ],
                admitted_gpa_distribution=_gpa_distribution(gpas),
                admission_year_range={"min": min(years) if years else None, "max": max(years) if years else None},
                source_record_count=len(school_programs) + len(school_cases),
            )
        )
    return schools
