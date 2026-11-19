"""Demo video script: scenes, narration and on-screen actions.

Every number here was measured in this repository (see docs/KIRO_NOTES.md and the reports).
Historical lines state only what the cited sources agree on (see .kiro/steering/product.md).

Tone: told as a story, short punchy beats, questions and reveals. The TTS (Kokoro) takes its
intonation from punctuation, so dashes, question marks and exclamations are deliberate.

Each scene has a page (a static-site URL fragment or a card under video/), narration
sentences, and actions keyed to a sentence: (sentence_index, seconds_after_it_starts, action).
An action is a JS snippet run in the page, or a ("click", selector, nth) tuple.

Look (see cards/fx.css): "grade" picks the ffmpeg colour grade, "theme" recolours the console,
"chapter" puts a chapter sting and tag over it. Cards reveal their lines with show().
"""


GEN_LAST = (
    "const r=document.querySelector('#gen-range'); r.value=r.max;"
    "r.dispatchEvent(new Event('input'))"
)
GEN_FIRST = (
    "const r=document.querySelector('#gen-range'); r.value=1;"
    "r.dispatchEvent(new Event('input'))"
)


def show(step: str) -> str:
    """JS that reveals a card's elements marked data-s=<step>."""
    return f"document.querySelectorAll('[data-s=\"{step}\"]').forEach(e => e.classList.add('on'))"


SCENES = [
    {
        "name": "title",
        "grade": "vhs",
        "page": "video/title.html",
        "lines": [
            "1981. A computer program enters a naval war game tournament — and wins.",
            "Its fleet? Ninety-six ships. Seventy-five of them, one cheap design.",
            "So the organisers change the rules. In 1982, it wins again — because the new "
            "rules let it destroy its own ships!",
            "Its name was Eurisko. It was built from heuristics — including heuristics that "
            "rewrote other heuristics.",
        ],
        "actions": [
            (0, 0.0, show("0")), (0, 3.2, show("0b")),
            (1, 0.0, show("1")), (2, 1.2, show("2")), (3, 0.0, show("3")),
        ],
    },
    {
        "name": "intro",
        "grade": "synth",
        "page": "video/intro.html",
        "lines": [
            "Meet Neurisko: Douglas Lenat's Eurisko, brought back to life with a large "
            "language model, and built with Kiro.",
            "Its mission? Find a game's exploits — before the players do.",
        ],
        "actions": [(0, 0.0, show("0")), (0, 1.6, show("0b")), (1, 0.4, show("1"))],
    },
    {
        "name": "tcs",
        "grade": "clean",
        "theme": "radar",
        "chapter": ("CH.1", "THE REMATCH", "TCS-lite · 1981 rules vs 1982 rules"),
        "page": "index.html#tcs",
        "lines": [
            "First, a rematch with history. TCS-lite is a small fleet game we wrote, in the "
            "spirit of that tournament.",
            "The starting heuristics know just one thing: build good warships.",
            "Under 1981 rules, it finds the swarm all by itself: ninety-nine tiny ships, and "
            "one escort.",
            "Now we add a 1982 rule: if too many ships are disabled, the fleet must withdraw. "
            "And the swarm collapses.",
            "Eight runs out of eight, the engine finds the loophole: scuttle your own "
            "disabled ships!",
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
        "grade": "clean",
        "theme": "pumpkin",
        "chapter": ("CH.2", "MONSTER MASH", "A Halloween auto-battler · live evolution"),
        "page": "index.html#run",
        "lines": [
            "Now for the real target: game designers. Welcome to Monster Mash — a Halloween "
            "auto-battler with twelve units.",
            "Every heuristic is plain data: if this holds, change the team. And its worth? "
            "Earned only in measured battles.",
            "A local Qwen model reads the evidence and invents new heuristics. In this run, "
            "four of the five best rules came from it!",
        ],
        "actions": [
            # A real battle first (the champion's, final generation), then the evolution.
            (0, 0.0, GEN_LAST),
            (0, 1.7, ("click", "#panel-run .battles button", 0)),
            (1, 0.0, ("click", "#battle-dialog .controls button", 4)),
            (1, 0.1, GEN_FIRST),
            (1, 0.6, ("click", "#btn-play", 0)),
        ],
    },
    {
        "name": "h59",
        "grade": "clean",
        "theme": "alarm",
        "chapter": ("CH.3", "H59", "Reward hacking, rebuilt on purpose"),
        "page": "index.html#h59",
        "lines": [
            "But Eurisko had a famous failure, too. Around 1983, a heuristic called H59 "
            "started taking credit for other heuristics' discoveries — and climbed to the "
            "top. Reward hacking.",
            "So we rebuilt that failure, on purpose. Auditor off? The Clone meta-heuristic "
            "tops the table, in eight seeds out of eight.",
            "Auditor on: caught, and demoted as a parasite. Every single time.",
        ],
        "actions": [],
    },
    {
        "name": "report",
        "grade": "clean",
        "theme": "clean",
        "chapter": ("CH.4", "THE REPORT", "What a designer actually gets"),
        "page": "index.html#report",
        "lines": [
            "So what does a designer actually get? A balance report. The witch shows up in "
            "ninety-five percent of strong teams — versus thirty-one percent of random ones.",
            "Every suggested fix is tested by evolving again. Not one single change worked. "
            "But the report found a combination that does: witch cost three, golem attack "
            "eight.",
            "And an LLM summary only makes the cut if every number in it matches the "
            "measurements.",
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
        "grade": "clean",
        "page": "video/kiro.html",
        "lines": [
            "Kiro built Neurisko. Six specs came before the code — and every time a "
            "measurement proved us wrong, the spec got fixed.",
            "Steering demands a source for every historical claim. Hooks run lint and tests "
            "on every change.",
            "And here's the twist: Neurisko is an MCP server. Open a ruleset in Kiro, ask "
            "\"is this balanced?\", and Kiro measures before it answers.",
            "When a quick check raised a false alarm, the full report caught it.",
        ],
        "actions": [
            (2, 0.0, "document.body.classList.add('step2')"),
            (3, 0.0, "document.body.classList.add('step3')"),
        ],
    },
    {
        "name": "end",
        "grade": "synth",
        "page": "video/end.html",
        "lines": [
            "Eurisko found exploits by accident. Neurisko finds them — on purpose.",
            "It's open source. And you can replay every single run, right in your browser.",
        ],
        "actions": [(0, 0.0, show("0")), (0, 2.0, show("0b")), (1, 0.0, show("1"))],
    },
]
