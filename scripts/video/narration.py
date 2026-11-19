"""Demo video script: scenes, narration and on-screen actions.

Every number here was measured in this repository (see docs/KIRO_NOTES.md and the reports).
Historical lines state only what the cited sources agree on (see .kiro/steering/product.md).

Each scene has a page (a static-site URL fragment or a card under video/), narration
sentences, and actions keyed to a sentence: (sentence_index, seconds_after_it_starts, action).
An action is a JS snippet run in the page, or a ("click", selector, nth) tuple.
"""

SCENES = [
    {
        "name": "title",
        "page": "video/title.html",
        "lines": [
            "In 1981, a program called Eurisko entered a naval war game tournament, and won.",
            "Its fleet had ninety-six ships, seventy-five of them one cheap design.",
            "The organisers changed the rules. In 1982 it won again, because the rules let it "
            "destroy its own ships.",
            "Eurisko was built from heuristics, including heuristics that rewrote other "
            "heuristics.",
        ],
        "actions": [],
    },
    {
        "name": "intro",
        "page": "video/intro.html",
        "lines": [
            "This is Neurisko: Douglas Lenat's Eurisko, rebuilt with a large language model, "
            "using Kiro.",
            "Its job: find a game's exploits before the players do.",
        ],
        "actions": [],
    },
    {
        "name": "tcs",
        "page": "index.html#tcs",
        "lines": [
            "First, we let it relive its own history, on TCS-lite, a small fleet game we wrote "
            "in the spirit of that tournament.",
            "Its starting heuristics only know one thing: build good warships.",
            "Under 1981 rules, it discovers the swarm on its own: ninety-nine minimal ships and "
            "one escort.",
            "Then we add a 1982 rule: a fleet with too many disabled ships must withdraw. The "
            "swarm collapses.",
            "In eight runs out of eight, the engine finds the way out: scuttle your own disabled "
            "ships.",
        ],
        "actions": [
            (1, 0.5, "document.querySelector('#h-diff').scrollIntoView({behavior:'smooth'})"),
            (2, 0.3, ("click", "#panel-tcs .battles button", 0)),
            (3, 0.0, ("click", "#battle-dialog .controls button", 4)),
            (3, 0.3, ("click", "#panel-tcs .battles button", 1)),
            (4, 0.0, ("click", "#battle-dialog .controls button", 4)),
            (4, 0.3, ("click", "#panel-tcs .battles button", 2)),
        ],
    },
    {
        "name": "run",
        "page": "index.html#run",
        "lines": [
            "Now the real target: game designers. This is Monster Mash, a Halloween auto-battler "
            "with twelve units.",
            "Every heuristic is data: if a condition holds, change the team. Worth comes only "
            "from measured battles.",
            "A local Qwen model invents new heuristics from the evidence. Four of the five best "
            "rules in this run came from it.",
        ],
        "actions": [
            (
                0,
                0.0,
                "const r=document.querySelector('#gen-range'); r.value=1;"
                "r.dispatchEvent(new Event('input'))",
            ),
            (0, 0.8, ("click", "#btn-play", 0)),
        ],
    },
    {
        "name": "h59",
        "page": "index.html#h59",
        "lines": [
            "Eurisko also had a famous failure. Around 1983, a heuristic called H59 took credit "
            "for other heuristics' discoveries, and rose to the top. Reward hacking.",
            "We rebuilt that failure on purpose. With the auditor off, the Clone meta-heuristic "
            "tops the table in eight of eight seeds.",
            "With the auditor on, it is caught and demoted as a parasite, every time.",
        ],
        "actions": [],
    },
    {
        "name": "report",
        "page": "index.html#report",
        "lines": [
            "What a designer gets is a balance report. The witch is in ninety-five percent of "
            "strong teams, against thirty-one percent of random ones.",
            "Every suggested fix is tested by evolving again. None of the single changes worked. "
            "The report found one that does: witch cost three, golem attack eight.",
            "An LLM summary is kept only if every number in it matches the measurements.",
        ],
        "actions": [
            (
                1,
                0.3,
                "document.querySelector('.patches').scrollIntoView({behavior:'smooth',"
                "block:'center'})",
            ),
            (2, 0.2, "window.scrollTo({top:0,behavior:'smooth'})"),
        ],
    },
    {
        "name": "kiro",
        "page": "video/kiro.html",
        "lines": [
            "Kiro built Neurisko. Six specs were written before the code, and corrected every "
            "time a measurement proved us wrong.",
            "Steering requires every historical claim to be sourced. Hooks run lint and tests "
            "on every change.",
            "And Neurisko is an MCP server. Open a ruleset in Kiro, ask if it is balanced, and "
            "Kiro measures before it answers.",
            "When a quick check gave a false positive, the full report caught it.",
        ],
        "actions": [
            (2, 0.0, "document.body.classList.add('step2')"),
            (3, 0.0, "document.body.classList.add('step3')"),
        ],
    },
    {
        "name": "end",
        "page": "video/end.html",
        "lines": [
            "Eurisko found exploits by accident. Neurisko finds them on purpose.",
            "It's open source, and you can replay every run in your browser.",
        ],
        "actions": [],
    },
]
