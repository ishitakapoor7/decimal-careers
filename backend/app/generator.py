import random

from app.storage.models import (
    EmploymentType,
    Job,
    SeniorityLevel,
    Team,
    WorkMode,
)

_TEAM_SKILLS: dict[Team, list[str]] = {
    Team.ENGINEERING: ["Python", "Go", "Postgres", "Kubernetes", "React", "AWS"],
    Team.SALES: ["Salesforce", "Prospecting", "Negotiation", "CRM", "Quota"],
    Team.PRODUCT: ["Roadmapping", "User Research", "SQL", "A/B Testing", "Figma"],
    Team.MARKETING: ["SEO", "HubSpot", "Content Strategy", "Analytics", "Email"],
    Team.DESIGN: ["Figma", "Prototyping", "Design Systems", "User Research", "CSS"],
    Team.FINANCE: ["Excel", "Modeling", "Forecasting", "GAAP", "SQL"],
    Team.OPERATIONS: ["Logistics", "Process Design", "SQL", "Vendor Mgmt", "Excel"],
}
_TITLES: dict[Team, str] = {
    Team.ENGINEERING: "Software Engineer",
    Team.SALES: "Account Executive",
    Team.PRODUCT: "Product Manager",
    Team.MARKETING: "Marketing Manager",
    Team.DESIGN: "Product Designer",
    Team.FINANCE: "Financial Analyst",
    Team.OPERATIONS: "Operations Manager",
}
_LEVEL_YEARS: dict[SeniorityLevel, int] = {
    SeniorityLevel.INTERN: 0,
    SeniorityLevel.ENTRY: 0,
    SeniorityLevel.MID: 3,
    SeniorityLevel.SENIOR: 6,
    SeniorityLevel.STAFF: 9,
}
_LEVEL_PREFIX: dict[SeniorityLevel, str] = {
    SeniorityLevel.INTERN: "Intern,",
    SeniorityLevel.ENTRY: "Junior",
    SeniorityLevel.MID: "",
    SeniorityLevel.SENIOR: "Senior",
    SeniorityLevel.STAFF: "Staff",
}
_LOCATIONS: list[tuple[str, str, str]] = [
    ("New York", "NY", "USA"),
    ("San Francisco", "CA", "USA"),
    ("Austin", "TX", "USA"),
    ("London", "England", "UK"),
    ("Bangalore", "Karnataka", "India"),
    ("Berlin", "Berlin", "Germany"),
]
# Deliberate phrasing variation (the "messiness").
_PHRASES: list[str] = [
    "We are looking for a {title} to join our {team} team.",
    "Join {team} as a {title} and make an impact.",
    "Our {team} org seeks an experienced {title}.",
    "{title} wanted — help us scale {team}.",
]


def generate(n: int, seed: int = 0) -> list[Job]:
    rng = random.Random(seed)
    teams = list(Team)
    jobs: list[Job] = []
    for i in range(n):
        team = rng.choice(teams)
        level = rng.choice(list(SeniorityLevel))
        emp = (
            EmploymentType.INTERNSHIP
            if level == SeniorityLevel.INTERN
            else rng.choice(
                [
                    EmploymentType.FULL_TIME,
                    EmploymentType.FULL_TIME,
                    EmploymentType.CONTRACT,
                ]
            )
        )
        city, state, country = rng.choice(_LOCATIONS)
        prefix = _LEVEL_PREFIX[level]
        base_title = _TITLES[team]
        title = f"{prefix} {base_title}".strip().strip(",").strip()
        pool = _TEAM_SKILLS[team]
        k = rng.randint(2, min(4, len(pool)))
        skills = rng.sample(pool, k)
        phrase = rng.choice(_PHRASES).format(title=base_title, team=team.value)
        req = "Required: " + ", ".join(skills[:2])
        nice = " Nice to have: " + ", ".join(skills[2:]) if len(skills) > 2 else ""
        description = f"{phrase} {req}.{nice}"
        jobs.append(
            Job(
                id=f"job-{seed}-{i}",
                title=title,
                team=team,
                employment_type=emp,
                seniority_level=level,
                min_years_exp=_LEVEL_YEARS[level],
                city=city,
                state_region=state,
                country=country,
                work_mode=rng.choice(list(WorkMode)),
                skills=skills,
                description=description,
            )
        )
    return jobs
