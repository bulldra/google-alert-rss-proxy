import main


def test_valid_url() -> None:
    result: bool = main.is_valid_url(
        "https://www.google.co.jp/alerts/feeds/12345678901234567890/12345678901234567\
890"
    )
    assert result is True


def test_taranslate() -> None:
    result: str = main.translate(
        "https://www.google.co.jp/alerts/feeds/12836160871432447773/91901909544411725\
12"
    )
    print(result)
    assert result is not None
    assert result.startswith("<?xml version='1.0' encoding='UTF-8'?>")
    assert result.endswith("</rss>\n")
    assert "Google アラート" in result


def test_get_canonical_url() -> None:
    assert main.get_canonical_url(None) is None
    assert main.get_canonical_url("") is None
    assert main.get_canonical_url("https://example.com") == "https://example.com"
    assert (
        main.get_canonical_url(
            "https://www.google.com/url?rct=j&sa=t&url=https://newspicks.com/news/95\
99747/body/&ct=ga&cd=CAIyHDhhM2JmZTQ3YWU1YjVjMjI6Y28uanA6amE6SlA&usg=AOvVaw3vDIV4RYg\
RtMJOxCK2NtR-"
        )
        == "https://newspicks.com/news/9599747/body/"
    )


def test_is_duplicate() -> None:

    titles: set[str] = {
        "ChatGPTを「業務効率化」にしか使わない人の盲点、新しいフロンティアを切り開くこともできる",
        "面倒なことはChatGPTにやらせよう",
    }

    assert main.is_duplicate(
        titles,
        "ChatGPTを「業務効率化」にしか使わない人の盲点、新しいフロンティアを切り開くこともできる",
    )

    assert main.is_duplicate(
        titles,
        "ChatGPTを「業務効率化」にしか使わない人の盲点 新しいフロンティアを切り開くこともできる",
    )

    assert main.is_duplicate(
        titles,
        "ChatGPTを「業務効率化」にしか使わない人の盲点",
    )

    assert not main.is_duplicate(
        titles,
        "ChatGPTで業務効率化しよう",
    )

    assert main.is_duplicate(
        titles,
        "面倒なことはChatGPTにやらせたい",
    )

    assert not main.is_duplicate(
        titles,
        "全てをChatGPTにやらせたい",
    )
