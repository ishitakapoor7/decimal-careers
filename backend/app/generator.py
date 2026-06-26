import datetime
import random

from app.storage.models import (
    EmploymentType,
    Job,
    SeniorityLevel,
    Team,
    WorkMode,
)

# Role variants: each team is a family of (title, skill-subpool) sub-specialties.
# A job picks ONE variant, so its title and skills are internally coherent and
# the team becomes a set of related sub-clusters (backend vs ML Engineering),
# which lets a resume match the right *kind* of role, not just the right team.
_ROLE_VARIANTS: dict[Team, list[tuple[str, list[str]]]] = {
    Team.ENGINEERING: [
        ("Backend Engineer", ["Python", "Go", "Postgres", "Redis", "Kubernetes",
                              "gRPC", "Docker", "REST APIs", "Microservices", "CI/CD"]),
        ("Frontend Engineer", ["React", "TypeScript", "CSS", "Next.js", "GraphQL",
                               "Webpack", "Accessibility", "Jest", "Tailwind", "Redux"]),
        ("Machine Learning Engineer", ["Python", "PyTorch", "LLMs", "Vector Databases",
                                       "CUDA", "MLflow", "Pandas", "Transformers",
                                       "Model Serving", "NumPy"]),
        ("DevOps Engineer", ["Terraform", "AWS", "Kubernetes", "CI/CD", "Prometheus",
                             "Docker", "Ansible", "Linux", "Observability", "Bash"]),
        ("Data Engineer", ["Python", "SQL", "Spark", "Airflow", "dbt", "Kafka",
                           "Snowflake", "ETL", "Data Modeling", "Postgres"]),
    ],
    Team.SALES: [
        ("Account Executive", ["Salesforce", "Prospecting", "Negotiation",
                               "Pipeline Management", "Closing", "Discovery",
                               "Quota Attainment", "Forecasting", "CRM"]),
        ("Sales Development Representative", ["Outbound", "Cold Calling",
                                             "Lead Qualification", "Salesforce",
                                             "Email Outreach", "Prospecting",
                                             "Cadence Tools", "CRM", "Research"]),
        ("Sales Engineer", ["Solution Selling", "Technical Demos", "Discovery",
                            "Integrations", "POCs", "Salesforce",
                            "Stakeholder Management", "Pre-sales", "APIs"]),
    ],
    Team.PRODUCT: [
        ("Product Manager", ["Roadmapping", "User Research", "SQL", "A/B Testing",
                             "Stakeholder Management", "Prioritization", "Analytics",
                             "Specs", "Go-to-Market"]),
        ("Technical Product Manager", ["APIs", "SQL", "System Design", "Roadmapping",
                                       "Data Analysis", "Experimentation",
                                       "Stakeholder Management", "Specs", "Platform"]),
        ("Growth Product Manager", ["Experimentation", "Funnel Analysis", "SQL",
                                    "A/B Testing", "Retention", "Analytics",
                                    "Activation", "Roadmapping", "Onboarding"]),
    ],
    Team.MARKETING: [
        ("Content Marketing Manager", ["SEO", "Content Strategy", "Copywriting",
                                       "Editorial", "Analytics", "CMS", "Storytelling",
                                       "Email", "Social Media"]),
        ("Growth Marketer", ["Paid Acquisition", "SEO", "Analytics", "A/B Testing",
                             "Email", "Funnel Optimization", "HubSpot", "Attribution",
                             "Landing Pages"]),
        ("Product Marketing Manager", ["Positioning", "Messaging", "Go-to-Market",
                                       "Competitive Analysis", "Sales Enablement",
                                       "Launches", "Analytics", "Research"]),
    ],
    Team.DESIGN: [
        ("Product Designer", ["Figma", "Prototyping", "User Research", "Design Systems",
                              "Interaction Design", "Wireframing", "Usability Testing",
                              "Accessibility"]),
        ("Brand Designer", ["Figma", "Visual Identity", "Typography", "Illustration",
                            "Brand Systems", "Adobe Creative Suite", "Motion", "Layout"]),
        ("UX Researcher", ["User Interviews", "Usability Testing", "Survey Design",
                           "Synthesis", "Personas", "Journey Mapping",
                           "Qualitative Research", "Data Analysis"]),
    ],
    Team.FINANCE: [
        ("Financial Analyst", ["Excel", "Financial Modeling", "Forecasting",
                               "Budgeting", "Variance Analysis", "SQL", "GAAP",
                               "Reporting"]),
        ("FP&A Manager", ["Financial Modeling", "Forecasting", "Budgeting", "Excel",
                          "Board Reporting", "Scenario Planning", "SQL", "KPIs"]),
        ("Accountant", ["GAAP", "Reconciliation", "QuickBooks", "Month-end Close",
                        "Accounts Payable", "Excel", "Audit", "Compliance"]),
    ],
    Team.OPERATIONS: [
        ("Operations Manager", ["Process Design", "Vendor Management", "Logistics",
                                "SQL", "Project Management", "KPIs", "Excel",
                                "Cross-functional"]),
        ("Business Operations Analyst", ["SQL", "Excel", "Process Improvement",
                                         "Dashboards", "Analytics",
                                         "Stakeholder Management", "Reporting",
                                         "Modeling"]),
        ("Supply Chain Analyst", ["Logistics", "Inventory Management", "Forecasting",
                                  "SQL", "Excel", "Vendor Management", "Procurement",
                                  "Planning"]),
    ],
}

def skill_vocabulary() -> set[str]:
    """The full set of skills any generated job can list. Shared as the lexicon
    for résumé skill extraction + the explanation-only skill-overlap signal, so
    "skills we look for in a résumé" stays in lockstep with "skills jobs ask for."
    """
    return {
        skill
        for variants in _ROLE_VARIANTS.values()
        for _title, skills in variants
        for skill in skills
    }


# Embedded role summary (the ONLY generated text that enters the vector). {title}
# is the variant title; varied phrasing keeps matching from being keyword-trivial.
_ROLE_SUMMARIES: dict[Team, list[str]] = {
    Team.ENGINEERING: [
        "As a {title}, you'll design, build, and operate the systems that power our products at scale.",
        "We're hiring a {title} to ship reliable, well-tested software and raise the engineering bar.",
        "Join us as a {title} to own services end-to-end, from design through production.",
        "As a {title}, you'll partner with product and design to turn ideas into robust features.",
        "We're looking for a {title} who loves clean code, fast iteration, and hard technical problems.",
    ],
    Team.SALES: [
        "As a {title}, you'll build relationships with prospects and close deals that grow our business.",
        "We're hiring a {title} to own a pipeline, run discovery, and consistently exceed quota.",
        "Join us as a {title} to bring our product to new customers and markets.",
        "As a {title}, you'll partner with prospects to understand their needs and earn their trust.",
        "We're looking for a {title} who is consultative, resilient, and driven by results.",
    ],
    Team.PRODUCT: [
        "As a {title}, you'll define the roadmap and ship products customers love.",
        "We're hiring a {title} to turn user insights into prioritized, measurable outcomes.",
        "Join us as a {title} to partner with engineering and design from idea to launch.",
        "As a {title}, you'll use data and research to decide what to build and why.",
        "We're looking for a {title} who balances vision, execution, and ruthless prioritization.",
    ],
    Team.MARKETING: [
        "As a {title}, you'll craft the story and campaigns that grow our audience.",
        "We're hiring a {title} to drive demand and measurable pipeline.",
        "Join us as a {title} to own positioning, messaging, and go-to-market.",
        "As a {title}, you'll blend creativity and analytics to reach the right people.",
        "We're looking for a {title} who turns data and narrative into growth.",
    ],
    Team.DESIGN: [
        "As a {title}, you'll shape intuitive, beautiful experiences end-to-end.",
        "We're hiring a {title} to turn complex problems into elegant, usable design.",
        "Join us as a {title} to partner with product and engineering on the full design process.",
        "As a {title}, you'll run research, prototype quickly, and sweat the details.",
        "We're looking for a {title} who pairs strong craft with deep user empathy.",
    ],
    Team.FINANCE: [
        "As a {title}, you'll turn numbers into the insights that guide our decisions.",
        "We're hiring a {title} to own models, forecasts, and reporting.",
        "Join us as a {title} to partner with leadership on planning and analysis.",
        "As a {title}, you'll bring rigor and clarity to our financial operations.",
        "We're looking for a {title} who is precise, analytical, and business-minded.",
    ],
    Team.OPERATIONS: [
        "As a {title}, you'll design the processes that keep our business running smoothly.",
        "We're hiring a {title} to drive efficiency across cross-functional operations.",
        "Join us as a {title} to turn messy problems into scalable systems.",
        "As a {title}, you'll partner across teams to remove bottlenecks and improve KPIs.",
        "We're looking for a {title} who is organized, analytical, and execution-focused.",
    ],
}

_RESPONSIBILITIES: dict[Team, list[str]] = {
    Team.ENGINEERING: [
        "Design, build, and maintain backend and frontend services.",
        "Write well-tested, maintainable code and review peers' pull requests.",
        "Collaborate with product and design to scope and deliver features.",
        "Improve system reliability, observability, and performance.",
        "Debug production issues and contribute to incident response.",
        "Mentor other engineers and shape technical direction.",
    ],
    Team.SALES: [
        "Build and manage a pipeline of qualified opportunities.",
        "Run discovery calls and tailored product demonstrations.",
        "Negotiate and close deals to meet or exceed quota.",
        "Partner with marketing and product on customer feedback.",
        "Maintain accurate forecasts and CRM hygiene.",
        "Develop relationships with key stakeholders and champions.",
    ],
    Team.PRODUCT: [
        "Define and prioritize the product roadmap.",
        "Translate user research and data into clear requirements.",
        "Partner with engineering and design through delivery.",
        "Define success metrics and measure outcomes.",
        "Communicate strategy and trade-offs to stakeholders.",
        "Run experiments and iterate based on results.",
    ],
    Team.MARKETING: [
        "Plan and execute multi-channel campaigns.",
        "Own content, messaging, and positioning.",
        "Analyze funnel performance and optimize conversion.",
        "Partner with sales on enablement and pipeline.",
        "Manage SEO, email, and social channels.",
        "Report on growth metrics and attribution.",
    ],
    Team.DESIGN: [
        "Design end-to-end flows from concept to high fidelity.",
        "Build and maintain components in the design system.",
        "Run user research and usability testing.",
        "Prototype and iterate quickly on feedback.",
        "Partner with engineering on faithful implementation.",
        "Advocate for accessibility and craft quality.",
    ],
    Team.FINANCE: [
        "Build and maintain financial models and forecasts.",
        "Own budgeting, variance analysis, and reporting.",
        "Partner with leadership on planning and scenarios.",
        "Ensure accuracy and compliance in financial records.",
        "Prepare board and investor materials.",
        "Improve financial processes and controls.",
    ],
    Team.OPERATIONS: [
        "Design and improve cross-functional processes.",
        "Manage vendors, logistics, and procurement.",
        "Build dashboards and track operational KPIs.",
        "Identify bottlenecks and drive efficiency.",
        "Partner across teams to execute key initiatives.",
        "Document and scale repeatable workflows.",
    ],
}

# Multi-company catalog: the platform matches across roles from many companies.
_COMPANIES: list[tuple[str, str]] = [
    ("Northwind Labs", "Northwind Labs builds developer tools used by thousands of engineering teams."),
    ("Volta Logistics", "Volta Logistics is reinventing freight with software-defined supply chains."),
    ("Lumen Health", "Lumen Health delivers AI-assisted care to millions of patients."),
    ("Castor Finance", "Castor Finance is a modern platform for treasury and corporate finance."),
    ("Pixel & Co", "Pixel & Co is a design-led studio crafting beloved consumer brands."),
    ("Meridian Retail", "Meridian Retail powers omnichannel commerce for global brands."),
    ("Atlas Robotics", "Atlas Robotics automates warehouses with autonomous systems."),
    ("Beacon Media", "Beacon Media is a next-generation content and streaming company."),
    ("Cobalt Security", "Cobalt Security protects enterprises with cloud-native security."),
    ("Vertex Analytics", "Vertex Analytics turns data into decisions for the Fortune 500."),
    ("Harbor Bank", "Harbor Bank is a digital-first bank for small businesses."),
    ("Solstice Energy", "Solstice Energy accelerates the transition to clean power."),
]

_BENEFITS: list[str] = [
    "Competitive salary and meaningful equity.",
    "Comprehensive medical, dental, and vision coverage.",
    "Unlimited PTO and flexible working hours.",
    "Annual learning and development budget.",
    "401(k) with company match.",
    "Generous parental leave.",
    "Home office and wellness stipends.",
    "Daily lunch and a fully stocked kitchen.",
]

# --- Prose qualification pools -------------------------------------------------
# Qualifications render as full sentences, not bare skill words. Skill NAMES are
# still woven in verbatim (so the JD stays concrete and scannable), but the vector
# never sees this prose — only `summary` + `skills` are embedded.

# Domain phrase that fits grammatically after "experience ...".
_TEAM_DOMAIN: dict[Team, str] = {
    Team.ENGINEERING: "building production software",
    Team.SALES: "selling B2B software",
    Team.PRODUCT: "shipping product",
    Team.MARKETING: "driving growth marketing",
    Team.DESIGN: "designing digital products",
    Team.FINANCE: "in finance or analytics",
    Team.OPERATIONS: "running business operations",
}

# Most internships require current enrollment, but a minority are open to recent
# grads too — uncommon, not impossible. INTERN_OPEN_TO_GRADS is the phrase the
# education gate (fit.job_requires_enrollment) keys off: its presence in a JD means
# "enrollment not required," so an already-graduated candidate isn't penalized for
# that role. The JD text stays the single source of truth — no schema flag.
INTERN_OPEN_TO_GRADS = "open to current students and recent grads"
_INTERN_ENROLLED_LINE = (
    "You're currently enrolled in a degree program and eager to get hands-on "
    "experience {domain}."
)
_INTERN_OPEN_LINE = (
    "This internship is " + INTERN_OPEN_TO_GRADS + " looking to get hands-on "
    "experience {domain}."
)

# Experience line, keyed to seniority. Display-only — does NOT reintroduce a
# filterable min_years_exp; the years are derived from seniority_level for reading.
# Intern is handled separately (see _experience_line) so it can vary enrollment.
_EXPERIENCE_LINE: dict[SeniorityLevel, str] = {
    SeniorityLevel.ENTRY: "You have 0–2 years of experience {domain}.",
    SeniorityLevel.MID: "You have 3+ years of hands-on experience {domain}.",
    SeniorityLevel.SENIOR: "You have 5+ years of experience {domain} and can operate independently.",
    SeniorityLevel.STAFF: "You have 8+ years of experience {domain} and a track record of leading complex initiatives.",
}

# Frames that weave the {skills} phrase into a sentence (required vs. preferred).
_SKILL_FRAMES: list[str] = [
    "You're proficient in {skills}.",
    "You have strong hands-on experience with {skills}.",
    "You're comfortable working across {skills}.",
    "You know your way around {skills}.",
]
_BONUS_FRAMES: list[str] = [
    "Bonus points if you've worked with {skills}.",
    "Familiarity with {skills} is a plus.",
    "Nice to have: exposure to {skills}.",
    "Experience with {skills} will help you hit the ground running.",
]

# Per-team disposition line — the "Philosophy/Approach" flavor that makes a JD read
# hand-written rather than templated.
_DISPOSITION: dict[Team, list[str]] = {
    Team.ENGINEERING: [
        "You write clean, well-tested code and care about reliability.",
        "You enjoy hard technical problems and fast iteration.",
        "You take ownership of services end-to-end.",
        "You communicate clearly and review others' work thoughtfully.",
        "You raise the engineering bar wherever you work.",
    ],
    Team.SALES: [
        "You're consultative, resilient, and motivated by hitting targets.",
        "You build trust quickly with prospects and stakeholders.",
        "You're organized and keep a clean pipeline.",
        "You stay genuinely curious about customers' problems.",
        "You thrive on ownership and accountability to a number.",
    ],
    Team.PRODUCT: [
        "You balance vision, execution, and ruthless prioritization.",
        "You let data and user research guide your decisions.",
        "You communicate strategy and trade-offs clearly.",
        "You partner closely with engineering and design.",
        "You sweat the details that make products great.",
    ],
    Team.MARKETING: [
        "You blend creativity with a sharp analytical edge.",
        "You turn data and narrative into measurable growth.",
        "You move fast and test relentlessly.",
        "You write clearly and persuasively.",
        "You care about the full funnel, not just the top.",
    ],
    Team.DESIGN: [
        "You pair strong craft with deep user empathy.",
        "You prototype quickly and iterate on feedback.",
        "You sweat the details and care about accessibility.",
        "You communicate design decisions with clarity.",
        "You raise the quality bar across the team.",
    ],
    Team.FINANCE: [
        "You're precise, analytical, and business-minded.",
        "You bring rigor and clarity to ambiguous problems.",
        "You can explain insights to non-financial partners.",
        "You're comfortable owning models end-to-end.",
        "You care about accuracy and the details.",
    ],
    Team.OPERATIONS: [
        "You're organized, analytical, and execution-focused.",
        "You turn messy problems into repeatable systems.",
        "You partner well across functions.",
        "You're comfortable owning ambiguous, cross-functional work.",
        "You care about measurable outcomes.",
    ],
}

# Generic aspirational closer for the "nice to have" section.
_ASPIRATIONAL: list[str] = [
    "You keep up with the latest developments in your field.",
    "You've thrived in a fast-paced, early-stage environment.",
    "You bring high agency and a bias for action.",
    "You care about doing great work with great people.",
]

# Second sentence of the "About the role" paragraph, per team.
_ROLE_ELABORATION: dict[Team, str] = {
    Team.ENGINEERING: "You'll partner with product and design to ship reliable, well-tested features that scale.",
    Team.SALES: "You'll own a pipeline end-to-end, from first touch to close.",
    Team.PRODUCT: "You'll work with engineering and design from first insight to launch.",
    Team.MARKETING: "You'll own campaigns end-to-end and measure what actually works.",
    Team.DESIGN: "You'll run the full design process, from research to polished, shippable work.",
    Team.FINANCE: "You'll own the models and reporting that guide our biggest decisions.",
    Team.OPERATIONS: "You'll design the processes that keep the business running smoothly.",
}

# Title prefix per level. "Junior" sits at MID (3+ yrs), not ENTRY: an entry-level
# role is 0–2 yrs, a junior role is a step up into mid-tier — so the title and the
# experience line below never contradict each other.
_LEVEL_PREFIX: dict[SeniorityLevel, str] = {
    SeniorityLevel.INTERN: "Intern,",
    SeniorityLevel.ENTRY: "Entry-level",
    SeniorityLevel.MID: "Junior",
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

# Coherent (display-only) salary: base by seniority, scaled by team and country.
_SENIORITY_BASE: dict[SeniorityLevel, int] = {
    SeniorityLevel.INTERN: 60_000,
    SeniorityLevel.ENTRY: 95_000,
    SeniorityLevel.MID: 140_000,
    SeniorityLevel.SENIOR: 185_000,
    SeniorityLevel.STAFF: 240_000,
}
_TEAM_MULT: dict[Team, float] = {
    Team.ENGINEERING: 1.15,
    Team.FINANCE: 1.10,
    Team.PRODUCT: 1.10,
    Team.DESIGN: 1.00,
    Team.SALES: 1.00,
    Team.MARKETING: 0.95,
    Team.OPERATIONS: 0.95,
}
_COUNTRY_MULT: dict[str, float] = {"USA": 1.0, "UK": 0.9, "Germany": 0.85, "India": 0.5}
_POST_ANCHOR = datetime.date(2026, 6, 25)


def _article(word: str) -> str:
    # Vowel-initial titles take "an" (Account, Operations); "U" stays "a" (UX).
    return "an" if word[:1] in "AEIOaeio" else "a"


def _round_5k(x: float) -> int:
    return int(round(x / 5_000) * 5_000)


def _salary(level: SeniorityLevel, team: Team, country: str) -> tuple[int, int]:
    base = _SENIORITY_BASE[level] * _TEAM_MULT[team] * _COUNTRY_MULT[country]
    return _round_5k(base), _round_5k(base * 1.3)


def _skill_phrase(skills: list[str]) -> str:
    # Oxford-comma join so skills read naturally inside a sentence.
    if len(skills) == 1:
        return skills[0]
    if len(skills) == 2:
        return f"{skills[0]} and {skills[1]}"
    return ", ".join(skills[:-1]) + f", and {skills[-1]}"


def _experience_line(level: SeniorityLevel, team: Team, rng: random.Random) -> str:
    """The experience sentence. For interns, occasionally (~1 in 4) the role is open
    to recent grads rather than requiring current enrollment."""
    if level == SeniorityLevel.INTERN:
        tmpl = _INTERN_OPEN_LINE if rng.random() < 0.25 else _INTERN_ENROLLED_LINE
    else:
        tmpl = _EXPERIENCE_LINE[level]
    return tmpl.format(domain=_TEAM_DOMAIN[team])


def _required_quals(
    level: SeniorityLevel, team: Team, required: list[str], rng: random.Random
) -> list[str]:
    """Three prose sentences: experience line, skills woven in, team disposition."""
    return [
        _experience_line(level, team, rng),
        rng.choice(_SKILL_FRAMES).format(skills=_skill_phrase(required)),
        rng.choice(_DISPOSITION[team]),
    ]


def _preferred_quals(preferred: list[str], rng: random.Random) -> list[str]:
    """A "bonus" line weaving the preferred skills, plus an aspirational closer."""
    quals: list[str] = []
    if preferred:
        quals.append(rng.choice(_BONUS_FRAMES).format(skills=_skill_phrase(preferred)))
    quals.append(rng.choice(_ASPIRATIONAL))
    return quals


def generate(n: int, seed: int = 0) -> list[Job]:
    rng = random.Random(seed)
    teams = list(Team)
    levels = list(SeniorityLevel)
    jobs: list[Job] = []
    for i in range(n):
        team = rng.choice(teams)
        base_title, pool = rng.choice(_ROLE_VARIANTS[team])
        level = rng.choice(levels)
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
        work_mode = rng.choice(list(WorkMode))

        prefix = _LEVEL_PREFIX[level]
        title = f"{prefix} {base_title}".strip().strip(",").strip()

        required = rng.sample(pool, min(rng.randint(2, 3), len(pool)))
        remaining = [s for s in pool if s not in required]
        preferred = (
            rng.sample(remaining, min(rng.randint(3, 5), len(remaining)))
            if remaining
            else []
        )
        skills = required + preferred

        company, company_about = rng.choice(_COMPANIES)
        summary = rng.choice(_ROLE_SUMMARIES[team]).format(title=base_title)
        summary = summary.replace(
            f"a {base_title}", f"{_article(base_title)} {base_title}", 1
        )
        about_role = f"{summary} {_ROLE_ELABORATION[team]}"

        resp_pool = _RESPONSIBILITIES[team]
        responsibilities = rng.sample(
            resp_pool, min(rng.randint(3, 5), len(resp_pool))
        )
        required_quals = _required_quals(level, team, required, rng)
        preferred_quals = _preferred_quals(preferred, rng)
        benefits = rng.sample(_BENEFITS, min(rng.randint(3, 5), len(_BENEFITS)))

        salary_min, salary_max = _salary(level, team, country)
        posted = _POST_ANCHOR - datetime.timedelta(days=rng.randint(0, 60))

        jobs.append(
            Job(
                id=f"job-{seed}-{i}",
                title=title,
                team=team,
                employment_type=emp,
                seniority_level=level,
                city=city,
                state_region=state,
                country=country,
                work_mode=work_mode,
                skills=skills,
                company=company,
                company_about=company_about,
                summary=summary,
                about_role=about_role,
                responsibilities=responsibilities,
                required_quals=required_quals,
                preferred_quals=preferred_quals,
                benefits=benefits,
                salary_min=salary_min,
                salary_max=salary_max,
                posted_date=posted.isoformat(),
            )
        )
    return jobs
