from seed_intel.extraction.deduplicator import find_duplicates, unique_projects
from seed_intel.extraction.schema import ProjectRecord


def test_project_deduplication():
    first = ProjectRecord(project_uid="a", project_name="项目A", source_url="https://www.seedasdan.com/a/", source_domain="www.seedasdan.com", extraction_method="rule", extraction_confidence=0.9)
    second = ProjectRecord(project_uid="b", project_name="项目A", source_url="https://www.seedasdan.com/a/", source_domain="www.seedasdan.com", extraction_method="rule", extraction_confidence=0.9)
    decisions = find_duplicates([first, second])
    assert decisions[0].duplicate_reason == "same_source_url"
    assert len(unique_projects([first, second])) == 1
