import pytest

from neurisko.cli import main


def test_battle_prints_log_and_result(capsys):
    assert main(["battle", "ghost,pumpkin_mage", "gargoyle,werewolf", "--seed", "3"]) == 0
    out = capsys.readouterr().out
    assert "hits" in out
    assert "TEAM B WINS" in out


def test_score_prints_report(capsys):
    assert main(["score", "zombie,ghost,witch"]) == 0
    out = capsys.readouterr().out
    assert "undead_swarm" in out
    assert "== SCORE" in out


def test_invalid_design_exits_2(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["score", "hellhound,hellhound,hellhound,lich"])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "unknown units: lich" in err
    assert "hellhound appears 3 times" in err


def test_invalid_ruleset_exits_2(tmp_path, capsys):
    bad = tmp_path / "bad.toml"
    bad.write_text('name = "x"\n')
    with pytest.raises(SystemExit) as exc:
        main(["battle", "zombie", "zombie", "--ruleset", str(bad)])
    assert exc.value.code == 2
    assert "limits: Field required" in capsys.readouterr().err
