from dianedu_archiver.supplement_articles import parse_candidate


def test_original_title_marker_and_explicit_repost_remain_a_candidate():
    html = ('<html><title>新标题</title><article><p>'+'公开正文。'*100+
            '</p><img alt="【夏校日记·13】茶余饭后——我在瑞克特瑞的夏天！"></article>'+
            '<footer>本文转载发布，版权归原作者所有</footer></html>').encode()
    result = parse_candidate(html, '【夏校日记·13】茶余饭后——我在瑞克特瑞的夏天！')
    assert result['status'] == 'attributed_same_work_candidate'
    assert result['original_body_byte_comparison_possible'] is False


def test_same_topic_without_original_identity_does_not_fill_body_gap():
    result = parse_candidate(('<article>'+'同主题不同文章。'*80+'</article>').encode(), '原文章标题')
    assert result['status'] == 'related_content_identity_unverified'
    assert parse_candidate(b'<html>please login</html>', 'title')['status'] == 'body_container_missing'


def test_saved_primary_page_article_detail_is_parsed_without_navigation():
    html=('<nav>无关导航</nav><div class="article__detail">'+'正文段落。'*80+'</div>').encode()
    result=parse_candidate(html,'原标题')
    assert result['status']=='related_content_identity_unverified'
    assert '无关导航' not in result['body_text']
