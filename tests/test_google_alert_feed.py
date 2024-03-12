from google_alert_feed import GoogleAlertsFeed


def test_valid_url() -> None:
    utils: GoogleAlertsFeed = GoogleAlertsFeed()
    result: bool = utils.is_valid_url(
        "https://www.google.co.jp/alerts/feeds/12345678901234567890/12345678901234567\
890"
    )
    assert result is True


def test_black_list_url() -> None:
    utils: GoogleAlertsFeed = GoogleAlertsFeed()
    result: bool = utils.is_black_list_url(
        "https://diamond.jp/articles/-/123456789012\
34567890"
    )
    assert result is True

    result: bool = utils.is_black_list_url(
        "https://diamojp/articles/-/123456789012\
34567890"
    )
    assert result is False


def test_simplification() -> None:
    utils: GoogleAlertsFeed = GoogleAlertsFeed()
    result: str = utils.simplification(
        "https://www.google.co.jp/alerts/feeds/12836160871432447773/91901909544411725\
12"
    )
    print(result)
    assert result is not None
    assert result.startswith("<?xml version='1.0' encoding='UTF-8'?>")
    assert result.endswith("</rss>\n")
    assert "Google アラート" in result


def test_get_canonical_url() -> None:
    utils: GoogleAlertsFeed = GoogleAlertsFeed()
    assert utils.get_canonical_url(None) is None
    assert utils.get_canonical_url("") is None
    assert utils.get_canonical_url("https://example.com") == "https://example.com"
    assert (
        utils.get_canonical_url(
            "https://www.google.com/url?rct=j&sa=t&url=https://newspicks.com/news/95\
99747/body/&ct=ga&cd=CAIyHDhhM2JmZTQ3YWU1YjVjMjI6Y28uanA6amE6SlA&usg=AOvVaw3vDIV4RYg\
RtMJOxCK2NtR-"
        )
        == "https://newspicks.com/news/9599747/body/"
    )


def test_is_duplicate() -> None:
    utils: GoogleAlertsFeed = GoogleAlertsFeed()
    utils._exist_titles: set[str] = {
        "ChatGPTを「業務効率化」にしか使わない人の盲点、新しいフロンティアを切り開くこともできる",
        "面倒なことはChatGPTにやらせよう",
    }

    assert utils.is_duplicate(
        "ChatGPTを「業務効率化」にしか使わない人の盲点、新しいフロンティアを切り開くこともできる",
    )

    assert utils.is_duplicate(
        "ChatGPTを「業務効率化」にしか使わない人の盲点 新しいフロンティアを切り開くこともできる",
    )

    assert utils.is_duplicate(
        "ChatGPTを「業務効率化」にしか使わない人の盲点",
    )

    assert not utils.is_duplicate(
        "ChatGPTで業務効率化しよう",
    )

    assert utils.is_duplicate(
        "面倒なことはChatGPTにやらせたい",
    )

    assert not utils.is_duplicate(
        "全てをChatGPTにやらせたい",
    )
