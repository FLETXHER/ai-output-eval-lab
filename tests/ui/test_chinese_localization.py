from __future__ import annotations

from pathlib import Path


EXPECTED_VISIBLE_LABELS = {
    "app.py": (
        "概览",
        "任务包",
        "测试用例",
        "Prompt 版本",
        "模型输出",
        "评测",
        "分析",
    ),
    "pages/overview.py": ("概览", "任务包", "测试用例", "Prompt 版本"),
    "pages/task_pack.py": ("任务包", "固定 MVP 合同", "数据集 QA"),
    "pages/test_cases.py": ("测试用例", "任务包", "数据集切分", "全部"),
    "pages/prompt_versions.py": ("Prompt 版本", "创建 Prompt 版本", "变更原因"),
    "pages/model_outputs.py": (
        "模型输出",
        "评测运行",
        "测试用例",
        "正式采集前确认生成模型条件",
        "可见模型",
        "确认生成模型条件",
        "可直接复制的生成任务包",
        "记录第一条实际回答",
        "模型原始回答",
        "生成时间",
        "保存实际回答",
        "记录技术故障重试",
    ),
    "pages/evaluation.py": ("评测", "盲化 Grader 导入", "盲化人工复核"),
    "pages/analysis.py": ("分析", "自动 calculated_status 汇总", "人工复核覆盖率"),
}


def test_primary_streamlit_labels_are_simplified_chinese(repo_root: Path) -> None:
    for relative_path, labels in EXPECTED_VISIBLE_LABELS.items():
        source = (repo_root / relative_path).read_text(encoding="utf-8")
        for label in labels:
            assert label in source, f"{relative_path} is missing localized label: {label}"


def test_model_outputs_page_does_not_keep_the_primary_english_workflow_labels(
    repo_root: Path,
) -> None:
    source = (repo_root / "pages" / "model_outputs.py").read_text(encoding="utf-8")
    for label in (
        'st.title("Model Outputs")',
        'st.selectbox("Evaluation Run"',
        'st.selectbox(\n        "Test Case"',
        'st.subheader("Copy-ready generation packet")',
        'st.form_submit_button("Record actual response")',
    ):
        assert label not in source
