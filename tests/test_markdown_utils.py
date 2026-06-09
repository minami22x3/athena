from markdown_utils import html_to_markdown, slugify


def test_slugify():
    assert slugify("How to Add a YouTube Video!") == "how-to-add-a-youtube-video"


def test_html_to_markdown_removes_noise():
    html = """
    <article>
      <h1>Title</h1>
      <p>Hello <a href="/docs">docs</a></p>
      <div class="article-votes">Was this article helpful?</div>
      <script>alert("x")</script>
    </article>
    """

    result = html_to_markdown(html)

    assert "# Title" in result
    assert "[docs](/docs)" in result
    assert "Was this article helpful?" not in result
    assert "alert" not in result
