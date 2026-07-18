from app.storage import (
    Artifact,
    append_artifact,
    append_message,
    create_conversation,
    list_artifacts,
)


def test_append_artifact_returns_metadata(storage_connection):
    conversation = create_conversation(
        storage_connection,
        selected_agent_ids=["supervisor"],
    )
    message = append_message(
        storage_connection,
        conversation_id=conversation.id,
        role="assistant",
        content="Here is a chart.",
        agent_name="supervisor",
    )

    artifact = append_artifact(
        storage_connection,
        conversation_id=conversation.id,
        message_id=message.id,
        artifact_type="chart",
        title="Revenue by Region",
        payload={
            "agent_id": "visualizer",
            "spec": {
                "chart_type": "bar",
                "title": "Revenue by Region",
                "series": [{"label": "West", "value": 10.0}],
            },
        },
    )

    assert isinstance(artifact, Artifact)
    assert artifact.id
    assert artifact.conversation_id == conversation.id
    assert artifact.message_id == message.id
    assert artifact.artifact_type == "chart"
    assert artifact.title == "Revenue by Region"
    assert artifact.payload["agent_id"] == "visualizer"
    assert artifact.payload["spec"]["series"] == [{"label": "West", "value": 10.0}]
    assert artifact.created_at


def test_list_artifacts_returns_conversation_artifacts_in_insert_order(
    storage_connection,
):
    conversation = create_conversation(
        storage_connection,
        selected_agent_ids=["supervisor"],
    )
    other_conversation = create_conversation(
        storage_connection,
        selected_agent_ids=["visualizer"],
    )

    first = append_artifact(
        storage_connection,
        conversation_id=conversation.id,
        message_id=None,
        artifact_type="chart",
        title="Revenue by Region",
        payload={"spec": {"title": "Revenue by Region"}},
    )
    second = append_artifact(
        storage_connection,
        conversation_id=conversation.id,
        message_id=None,
        artifact_type="chart",
        title="Revenue by Month",
        payload={"spec": {"title": "Revenue by Month"}},
    )
    append_artifact(
        storage_connection,
        conversation_id=other_conversation.id,
        message_id=None,
        artifact_type="chart",
        title="Separate",
        payload={"spec": {"title": "Separate"}},
    )

    assert list_artifacts(storage_connection, conversation.id) == [first, second]
