from google_alert_feed import GoogleAlertsFeed


def test_valid_url() -> None:
    utils: GoogleAlertsFeed = GoogleAlertsFeed()
    result: bool = utils.is_valid_url(
        "https://www.google.co.jp/alerts/feeds/1234567890"
        "1234567890/12345678901234567890"
    )
    assert result is True


def test_is_black_list_url() -> None:
    utils: GoogleAlertsFeed = GoogleAlertsFeed()

    assert (
        utils.is_black_list_url("https://diamond.jp/articles/-/12345678901234567890")
        is True
    )
    assert (
        utils.is_black_list_url("https://diamojp/articles/-/12345678901234567890")
        is False
    )
    assert (
        utils.is_black_list_url("https://expresso222.com.br/list/57_13844_58?kg=dy")
        is True
    )
    assert (
        utils.is_black_list_url("https://expresso222.com/list/57_13844_58?kg=dy")
        is False
    )
    assert (
        utils.is_black_list_url("https://qiita.com/kabumira/12345678901234567890")
        is True
    )
    assert (
        utils.is_black_list_url(
            "https://lewiscs.com/c/%E6%97%A5%E6%9C%AC-%E3"
            "%81%AE-%E3%83%88%E3%83%AC%E3%83%B3%E3%83%89"
        )
        is True
    )
    assert (
        utils.is_black_list_url(
            "https://propertyratings.co.in/c/web-%E3%83%9E"
            "%E3%83%BC%E3%82%B1%E3%83%86%E3%82%A3%E3%83%B3%E3%82%B0-%E3%81%A8-%E3%81%AF"
        )
        is True
    )


def test_simplification() -> None:
    utils: GoogleAlertsFeed = GoogleAlertsFeed()
    result: str = utils.simplification(
        "https://www.google.co.jp/alerts/feeds/12836160871432447773/6221419027880576930"
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
