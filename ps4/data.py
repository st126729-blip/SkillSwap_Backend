"""Synthetic content for the PS4 pages. Personas are composites, not real people."""

PERSONAS = {
    "khoa": {
        "slug": "khoa",
        "name": "Khoa",
        "label": "The Side-Project Builder (project owner)",
        "background": "A developer who builds side projects after work. Strong at code, "
        "but his interfaces look rough and he has no budget to hire a designer.",
        "short_goal": "Find a designer for his app and agree exactly what will be delivered.",
        "long_goal": "Ship a polished product and build a reliable circle of collaborators.",
        "tasks": [
            "Review a partner's portfolio links",
            "Create a project and milestones with completion conditions",
            "Fund and review a milestone",
            "Approve, request changes or dispute",
        ],
        "frustrations": [
            "A design that could not be built was discovered late",
            "Tasks and discussion live in different tools",
            "Partners outside IT find developer tools overwhelming",
        ],
        "tech": "Works on a laptop; uses his phone only for short messages.",
        "expectations": [
            "A written scope per milestone before work starts",
            "Links to repositories or design files on each task",
            "A visible track record of the partner",
        ],
        "evidence": "Anonymised interviews P1 and P3 (findings I2, I3, I5).",
        "scenario": {
            "title": "Khoa agrees scope with a designer (laptop)",
            "trigger": "His expense-tracking app looks rough and he wants a designer for the main dashboard.",
            "steps": [
                "Checks the partner's portfolio links.",
                "Creates a project and a first milestone with the deliverable and completion condition.",
                "Attaches a link to his current Figma file.",
                "Invites the designer and funds the milestone.",
                "When work is submitted, checks it against the condition and approves.",
            ],
            "outcome": "After both sides approve, the credits are released and the ledger records it.",
            "exception": "The submitted layout cannot be built as drawn. Khoa raises a dispute with a "
            "reason, the milestone is frozen as DISPUTED and staff resolve it.",
        },
    },
    "nam": {
        "slug": "nam",
        "name": "Nam",
        "label": "The Freelance Creative (collaborator, mobile scenario)",
        "background": "A freelance designer and video editor who often works at night and "
        "sometimes needs a writer or another specialist.",
        "short_goal": "Deliver client work on time with a partner who answers and delivers.",
        "long_goal": "Steady collaborations and a stronger personal reputation.",
        "tasks": [
            "Agree deliverables and deadlines in one place",
            "Submit work with a note and a link",
            "Check milestone status and wallet",
            "Reply to quick updates on his phone",
        ],
        "frustrations": [
            "A helper disappeared near a deadline",
            "Partners keep different hours and are hard to reach",
            "Searching old messages to see what changed",
        ],
        "tech": "Laptop for large files; phone for quick replies and checks. "
        "Large files and detailed edits are hard on a small screen.",
        "expectations": [
            "One page with who does what, the deadline and the completion standard",
            "A deposit or escrow before work starts",
            "Changes visible without searching old messages",
        ],
        "evidence": "Anonymised interview P5 only (findings I1, I2, I4, I5, I6). Evidence for "
        "this persona and for mobile use is limited.",
        "scenario": {
            "title": "Nam checks an escrowed milestone on his phone (mobile)",
            "trigger": "A client sends Nam a milestone link in a chat while he is away from his laptop.",
            "steps": [
                "Opens the link on his phone and logs in.",
                "Reads the milestone card: deliverable, deadline and completion condition.",
                "Sees the status FUNDED, meaning the credits are held in escrow.",
                "Replies in chat that he will start tonight.",
                "Later, from the same phone, checks that the status and wallet are unchanged.",
            ],
            "outcome": "Nam starts work knowing the payment is secured and what counts as done.",
            "exception": "The final file is too large to handle on the phone. He submits a link to the "
            "file from his laptop and keeps the phone for status checks.",
        },
    },
    "ha": {
        "slug": "ha",
        "name": "Ha",
        "label": "The Milestone Coordinator (hiring and reviewing)",
        "background": "A product manager who brings in freelancers when the team is overloaded. "
        "She cares about scope, acceptance criteria and fair payment.",
        "short_goal": "Get a freelancer's module delivered on a known date, with early warning if it slips.",
        "long_goal": "A repeatable way to hire short-term help without surprises.",
        "tasks": [
            "Write scope and milestones with acceptance criteria",
            "Fund each milestone",
            "Review submissions",
            "Request changes or approve and keep a history",
        ],
        "frustrations": [
            "A freelancer gave no early warning, so the team worked through a weekend",
            "Unclear whether 'done' means finished or waiting for review",
            "Partners available only in the evening",
        ],
        "tech": "Laptop most of the time; phone mainly to approve quick notifications.",
        "expectations": [
            "Milestones tied to acceptance conditions and release amounts",
            "A clear awaiting-review state and a way to request changes with a note",
            "Escrow",
        ],
        "evidence": "Anonymised interviews P2 and P3 (findings I1, I4, I6) and P2's prototype feedback.",
        "scenario": {
            "title": "Ha reviews a submission, starting on her phone",
            "trigger": "A freelancer reports that a payment-integration module is ready.",
            "steps": [
                "On her phone she sees the milestone marked 'Awaiting review' and reads the conditions.",
                "She cannot check the submitted link properly on a small screen, so she moves to her laptop.",
                "She opens the link and checks each acceptance condition.",
                "If all are met she approves and waits for the freelancer's approval.",
                "Once both approved, the milestone is RELEASED and the history shows who approved and when.",
            ],
            "outcome": "The milestone is released and the history is complete.",
            "exception": "One condition is not met. She requests changes with a note instead of "
            "approving (a planned feature: the first prototype had no such option).",
        },
    },
}

FINDINGS = [
    ("I1", "A partner who fails to deliver, or warns too late, is costly.", "Escrow, a visible submission record and a dispute path."),
    ("I2", "Vague scope and expectations cause rework and arguments.", "Each milestone states deliverable, amount and completion condition before funding."),
    ("I3", "Trust in strangers comes from visible evidence, then small trial work.", "Portfolio links on profiles; encourage small first milestones."),
    ("I4", "Milestone payments and deposits are already normal in professional work.", "Keep the milestone workflow as the core feature."),
    ("I5", "Tools are fragmented; non-technical partners struggle with technical tools.", "One simple status view, plain wording."),
    ("I6", "Laptops are the main work device; phones are for quick checks.", "Compact mobile views for status and approval."),
]

ROLES = [
    ("Anonymous visitor", "View public PS4 pages; register; verify email. No access to projects or wallets."),
    ("Registered user", "Create projects; see and edit only their own profile and wallet."),
    ("Project owner", "Create and fund milestones; approve as owner; request changes; dispute."),
    ("Collaborator", "Submit work; approve as collaborator; dispute."),
    ("Staff", "Resolve disputes; read-only audit of what a dispute needs."),
]

STORIES = [
    ("Must", "As a project owner I can create a milestone with a deliverable, completion condition and credit amount, so that expectations are clear before funding."),
    ("Must", "As a project owner I can fund a milestone from my wallet, so that my partner knows the credits are secured."),
    ("Must", "As a collaborator I can submit work with a note and a link, so that the owner can review it."),
    ("Must", "As a project member I can release a milestone only after both sides approve, and never twice."),
    ("Must (permissions)", "As a user who is not a member of a project I cannot see or change it."),
    ("Must (privacy)", "As a user I can see only my own wallet and ledger."),
    ("Should", "As a project owner I can request changes with a note, so that rework is recorded."),
]

MVP = {
    "in": [
        "Registration, email verification and login",
        "Projects and milestones with deliverable and completion condition",
        "Funding into escrow and wallet ledger",
        "Submit work with note and link; dual approval; release once",
        "Refund and dispute with staff resolution",
        "Awaiting-review status and request-changes with a note",
        "Reference link on a milestone; plain wording",
        "Responsive status and approval view for phones",
    ],
    "out": [
        "Activity feed and groups",
        "Reputation and vouching interface",
        "User search and discovery",
        "Email or push notifications",
        "Revenue share or equity payment",
        "Converting credits to money",
    ],
}
