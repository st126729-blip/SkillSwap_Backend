"""Synthetic, evidence-based personas for PS4.

These are composite profiles. They contain no real names, ages, photos or
private interview notes. Participant codes (P1, P2, ...) refer to the
anonymized interview findings in the project report.
"""

PERSONAS = {
    "khoa": {
        "slug": "khoa",
        "name": "Khoa",
        "label": "The Side-Project Builder",
        "role": "Project owner who needs help outside his own skills",
        "background": (
            "A developer who builds side projects after work. He is strong in "
            "frontend and backend code, but his interfaces look rough and he "
            "has no budget to hire a designer."
        ),
        "short_goal": "Find a designer for his current app and agree exactly what will be delivered.",
        "long_goal": "Ship a polished product and build a reliable circle of collaborators.",
        "tasks": [
            "Post what help he needs and review a partner's portfolio",
            "Create a project and split it into milestones with clear completion conditions",
            "Fund a milestone and check the submitted work",
            "Approve, request changes or raise a dispute",
        ],
        "frustrations": [
            "A designer's work looked good but was not feasible to build, discovered only at coding time",
            "Tasks live in one tool while discussion happens in another chat app",
            "Partners outside IT feel overwhelmed by developer tools",
        ],
        "constraints": "Works on a laptop; checks his phone only for short messages.",
        "expectations": [
            "A written scope for every milestone before any work starts",
            "Links to repositories or design files attached to each task",
            "A visible track record (portfolio) of the partner",
        ],
        "evidence": [
            ("P1", "Lost a week after a stranger designer's dashboard turned out to be infeasible; asks for GitHub or portfolio links and gives a 1-2 day trial task."),
            ("P1", "Task tracking and discussion end up in different tools; designers find Jira overwhelming."),
            ("P3", "Needs a lightweight shared space for partners who are not technical."),
        ],
        "scenario_title": "Khoa agrees scope with a designer",
        "scenario": {
            "device": "Laptop",
            "trigger": "Khoa's expense-tracking app looks rough and he wants a designer to redo the main dashboard.",
            "steps": [
                "He opens a partner's profile and checks the portfolio links.",
                "He creates a project and a first milestone for the dashboard design, writing the deliverable and the completion condition.",
                "He attaches a link to his current Figma file and invites the designer.",
                "He funds the milestone; the credits are held in escrow.",
                "When the designer submits the work, he checks it against the condition and approves.",
            ],
            "outcome": "After both sides approve, the credits are released and the ledger records the release.",
            "exception": (
                "The submitted layout cannot be built as drawn. Khoa raises a dispute with a "
                "reason instead of approving, the milestone is frozen as DISPUTED, and staff resolve it."
            ),
        },
    },
    "nam": {
        "slug": "nam",
        "name": "Nam",
        "label": "The Freelance Creative",
        "role": "Collaborator who delivers design and motion work",
        "background": (
            "A freelance designer and video editor who often works late at night. "
            "He sometimes needs a writer or another specialist to finish a project."
        ),
        "short_goal": "Deliver client work on time with a partner who answers and delivers.",
        "long_goal": "Steady collaborations and a stronger personal reputation.",
        "tasks": [
            "Agree deliverables, deadlines and completion standard in one place",
            "Submit work with a note and a link",
            "Check milestone status and wallet balance",
            "Answer quick updates from his phone",
        ],
        "frustrations": [
            "A helper accepted a job and then disappeared close to the deadline",
            "Needing a quick answer when the partner is asleep in a different schedule",
            "Having to search old chat messages to find what changed",
        ],
        "constraints": (
            "Works mainly on a laptop because of large files; uses the phone for quick replies "
            "and checking notices. Large files and detailed edits are hard on a small screen."
        ),
        "expectations": [
            "One page showing who does what, the deadline and the completion standard",
            "Automatic notices to both sides when something changes",
            "A deposit or escrow before work starts",
        ],
        "evidence": [
            ("P5", "A 3D helper vanished near the deadline, costing two nights of extra work."),
            ("P5", "Prefers money and a 50% deposit; ideal project is one page with owner, deadline and completion standard, with automatic change notices."),
            ("P5", "Laptop for heavy files, phone only for quick replies; schedule often differs from partners."),
            ("P5 (prototype test)", "Understood the progress overview on a phone but struggled to edit details or review large files there."),
        ],
        "scenario_title": "Nam approves a milestone from his phone",
        "scenario": {
            "device": "Mobile phone (quick review)",
            "trigger": "A notice arrives that the project owner has approved Nam's milestone while he is out of the house.",
            "steps": [
                "He opens the notification and lands on the milestone summary.",
                "He sees the status and that only the owner has approved so far.",
                "He taps Approve to give his own approval.",
                "He checks that the status changes to RELEASED and the credits appear in his wallet.",
            ],
            "outcome": "The credits are released after both approvals and appear in his wallet history.",
            "exception": (
                "The connection drops when he taps Approve. The page shows an error, and after "
                "reloading he can see the milestone is still waiting for his approval, so he taps again "
                "without creating a duplicate release. Detailed edits and large files are left "
                "for his laptop."
            ),
        },
    },
    "ha": {
        "slug": "ha",
        "name": "Ha",
        "label": "The Milestone Coordinator",
        "role": "Coordinator who hires outside help and signs off on delivery",
        "background": (
            "A product manager who plans work for a team and brings in freelancers when the team is "
            "overloaded. She cares about scope, acceptance criteria and getting paid or paying fairly."
        ),
        "short_goal": "Get a freelancer's module delivered on a known date, with early warning if it slips.",
        "long_goal": "A repeatable way to hire short-term help without surprises.",
        "tasks": [
            "Write the scope and split it into milestones with acceptance criteria",
            "Fund each milestone and track progress",
            "Review submissions, request changes or approve",
            "Keep a history of what was agreed and changed",
        ],
        "frustrations": [
            "A freelancer misjudged the work and gave no early warning, so the team worked through a weekend",
            "Unclear whether 'done' means finished or waiting for review",
            "Partners online only in the evening, hard to sync with office hours",
        ],
        "constraints": "Works on a laptop; uses the phone mainly to approve quick notifications.",
        "expectations": [
            "Milestones tied to acceptance conditions and release amounts",
            "A clear 'pending review' state and a way to request changes with a note",
            "Escrow so both sides feel protected",
        ],
        "evidence": [
            ("P2", "Splits work by scope and milestone: part paid at API done, part at acceptance testing, remainder at handover."),
            ("P2", "A freelancer did not warn early about a missed demo; the team had to work through a weekend."),
            ("P2 (prototype test)", "Unsure whether pressing 'complete' finalises or waits for approval; asked for a pending-review state and a request-changes button."),
            ("P2", "Names escrow and automatic updates to tasks as part of an ideal project."),
        ],
        "scenario_title": "Ha reviews a submission and asks for changes",
        "scenario": {
            "device": "Laptop",
            "trigger": "A freelancer reports that a payment-integration module is ready for review.",
            "steps": [
                "She opens the milestone and reads the acceptance conditions she wrote.",
                "She opens the submitted link and checks each condition.",
                "She approves the milestone and waits for the freelancer's approval.",
                "Once both have approved, the milestone is RELEASED and she can see it in the history.",
            ],
            "outcome": "The milestone is released and its history shows who approved and when.",
            "exception": (
                "One condition is not met. There is no 'request changes' option in the current "
                "prototype, so she must dispute or message outside the platform. This gap is "
                "listed as a design change in the prototype feedback."
            ),
        },
    },
}

PERSONA_ORDER = ["khoa", "nam", "ha"]
