"""KNIME nodes that ask AIsolate airlocks: a connector that signs in, a selector that picks the airlock,
a prompter that asks it, one question per row."""

import knime.extension as knext
import pandas as pd

import aisolate_client as aisolate

ICON = "icons/aisolate.png"  # the full AIsolate mark
AIRLOCK_ICON = "icons/airlock.png"  # the hex nut

category = knext.category(
    path="/",
    level_id="aisolate",
    name="AIsolate",
    description="Ask AIsolate airlocks: governed answers with their provenance.",
    icon=ICON,
)


class AIsolateSpec(knext.PortObjectSpec):
    """The release, the credentials flow variable that signs in to it, and the airlocks it admits.

    Holds no token: each node signs in again from the credentials, which KNIME keeps out of the workflow file.
    """

    def __init__(self, url: str, credentials: str, token_url: str = "", airlocks: list | None = None) -> None:
        self.url, self.credentials, self.token_url, self.airlocks = url, credentials, token_url, airlocks or []

    def serialize(self) -> dict:
        return {"url": self.url, "credentials": self.credentials, "token_url": self.token_url, "airlocks": self.airlocks}

    @classmethod
    def deserialize(cls, data: dict) -> "AIsolateSpec":
        return cls(data["url"], data["credentials"], data.get("token_url", ""), data.get("airlocks"))


class AirlockSpec(knext.PortObjectSpec):
    """One airlock of the release: its chat endpoint. Holds no token either."""

    def __init__(self, url: str, credentials: str, token_url: str = "", endpoint: str = "") -> None:
        self.url, self.credentials, self.token_url, self.endpoint = url, credentials, token_url, endpoint

    def serialize(self) -> dict:
        return {"url": self.url, "credentials": self.credentials, "token_url": self.token_url, "endpoint": self.endpoint}

    @classmethod
    def deserialize(cls, data: dict) -> "AirlockSpec":
        return cls(data["url"], data["credentials"], data.get("token_url", ""), data.get("endpoint", ""))


class AIsolatePortObject(knext.PortObject):
    def serialize(self) -> bytes:
        return b""

    @classmethod
    def deserialize(cls, spec: AIsolateSpec, storage: bytes) -> "AIsolatePortObject":
        return cls(spec)


class AirlockPortObject(knext.PortObject):
    def serialize(self) -> bytes:
        return b""

    @classmethod
    def deserialize(cls, spec: AirlockSpec, storage: bytes) -> "AirlockPortObject":
        return cls(spec)


aisolate_port = knext.port_type("AIsolate", AIsolatePortObject, AIsolateSpec)
airlock_port = knext.port_type("Airlock", AirlockPortObject, AirlockSpec)


def _credential_names(ctx):
    return ctx.get_credential_names() if ctx else []


@knext.node("AIsolate Connector", knext.NodeType.SOURCE, ICON, category)
@knext.output_port("AIsolate", "The release, signed in, with the airlocks this client may ask.", aisolate_port)
class AIsolateConnector:
    """Signs in to AIsolate with a client's id and secret and lists the airlocks it may ask.

    Give the release's URL and a credentials flow variable holding the client's id and secret, for instance from a
    **Credentials Configuration** node. The connector finds the identity provider from the release itself
    (`/.well-known/oauth-protected-resource`), signs in with the client-credentials grant and lists the airlocks
    that admit the client. Connect an **Airlock Selector** to pick one.

    The token never leaves the node: the prompter signs in again from the same credentials.
    """

    url = knext.StringParameter("AIsolate URL", "The release, e.g. `https://aisolate.example.com`.", "http://aisolate.localhost")
    credentials = knext.StringParameter(
        "Client credentials",
        "The credentials flow variable with the client id (user name) and the client secret (password).",
        "client",
        choices=_credential_names,
    )

    def configure(self, ctx: knext.ConfigurationContext) -> AIsolateSpec:
        if not self.credentials:
            raise knext.InvalidParametersError("Select the credentials flow variable with the client id and secret.")
        return AIsolateSpec(self.url, self.credentials)

    def execute(self, ctx: knext.ExecutionContext) -> AIsolatePortObject:
        client = ctx.get_credentials(self.credentials)
        token_url = aisolate.token_endpoint(self.url)
        found = aisolate.airlocks(self.url, aisolate.sign_in(token_url, client.username, client.password))
        if not found:
            ctx.set_warning("No airlock admits this client: list its client id in an airlock's access.clients.")
        return AIsolatePortObject(AIsolateSpec(self.url, self.credentials, token_url, found))


def _airlock_choices(ctx):
    specs = ctx.get_input_specs() if ctx else []
    spec = specs[0] if specs else None
    if not isinstance(spec, AIsolateSpec):
        return []
    return [knext.StringParameter.Choice(endpoint, label, description)
            for endpoint, label, description in aisolate.choices(spec.airlocks)]


@knext.node("Airlock Selector", knext.NodeType.SOURCE, AIRLOCK_ICON, category)
@knext.input_port("AIsolate", "From an AIsolate Connector.", aisolate_port)
@knext.output_port("Airlock", "The airlock to ask.", airlock_port)
class AirlockSelector:
    """Picks the airlock to ask, from the ones the client may ask.

    Execute the **AIsolate Connector** first to fill the list. Left empty, the selector picks the first airlock
    the client may ask. Connect an **Airlock Prompter** to ask it.
    """

    airlock = knext.StringParameter(
        "Airlock", "The airlock to ask; empty picks the first one the client may ask.",
        choices=_airlock_choices)

    def configure(self, ctx: knext.ConfigurationContext, spec: AIsolateSpec) -> AirlockSpec:
        return AirlockSpec(spec.url, spec.credentials, spec.token_url, self.airlock)

    def execute(self, ctx: knext.ExecutionContext, port: AIsolatePortObject) -> AirlockPortObject:
        spec = port.spec
        found = aisolate.choices(spec.airlocks)
        chosen = [a for a in found if a[0] == self.airlock] if self.airlock else found[:1]
        if not chosen:
            raise knext.InvalidParametersError(
                "This client may not ask that airlock." if self.airlock else
                "No airlock admits this client: list its client id in an airlock's access.clients.")
        endpoint, *_ = chosen[0]
        return AirlockPortObject(AirlockSpec(spec.url, spec.credentials, spec.token_url, endpoint))


class MissingValues(knext.EnumParameterOptions):
    OUTPUT_MISSING = ("Output missing values", "A row without a question gets missing values and is not asked.")
    FAIL = ("Fail", "A row without a question stops the node.")


def _answer_columns(answer_column: str) -> list:
    return [
        (answer_column, "answer", knext.string()), ("provenance", "provenance", knext.string()),
        ("sourced", "sourced", knext.int64()), ("computed", "computed", knext.int64()),
        ("unsourced", "unsourced", knext.int64()), ("mismatch", "mismatch", knext.int64()),
        ("evidence", "evidence", knext.string()), ("revision", "revision", knext.string()),
        ("trace_id", "trace_id", knext.string()),
    ]


@knext.node("Airlock Prompter", knext.NodeType.PREDICTOR, AIRLOCK_ICON, category)
@knext.input_port("Airlock", "From an Airlock Selector.", airlock_port)
@knext.input_table("Questions", "Optional: one question per row. Without it, the node asks its own question.", optional=True)
@knext.output_table("Answers", "The questions, each with its answer, provenance and evidence.")
class AirlockPrompter:
    """Asks an AIsolate airlock each question and returns the answer with its provenance.

    Type a question, or connect a table and pick the column with the questions. Each row gets the answer and what it
    rests on:

    - **answer** (or the name you give it): the text, every figure written in by AIsolate from the evidence
    - **provenance**: `all_sourced`, `has_unsourced`, `has_mismatch` or `no_figures`, with the counts
      **sourced**, **computed**, **unsourced** and **mismatch**; route anything but `all_sourced` to a person
    - **evidence**: the entries the answer rests on (id, tool, entity, row count, data source), never the rows
    - **revision** and **trace_id**: the release that answered and the exchange's trace in the audit log

    The answer may only rest on rows the client may read: a row it may not read never reaches the model. The
    airlock's own prompt and rules apply; a workflow cannot replace them.
    """

    question = knext.MultilineStringParameter(
        "Question", "The question to ask when no table is connected.", "What is John Doe's notice period?")
    question_column = knext.ColumnParameter(
        "Question column", "With a table connected: the column with the questions.", port_index=1,
        column_filter=lambda column: column.ktype == knext.string(),
    )
    missing_values = knext.EnumParameter(
        "If there are missing values", "What a row without a question does.",
        MissingValues.FAIL.name, MissingValues, style=knext.EnumParameter.Style.VALUE_SWITCH)
    answer_column = knext.StringParameter("Answer column name", "The name of the column with the answers.", "answer")

    def configure(self, ctx: knext.ConfigurationContext, spec: AirlockSpec, questions: knext.Schema | None) -> knext.Schema:
        if not self.answer_column.strip():
            raise knext.InvalidParametersError("Give the answer column a name.")
        if questions is None:
            questions = knext.Schema.from_columns([knext.Column(knext.string(), "question")])
        elif not self.question_column:
            raise knext.InvalidParametersError("Pick the column with the questions.")
        for name, _, ktype in _answer_columns(self.answer_column):
            if name in questions.column_names:
                raise knext.InvalidParametersError(f"The table already has a column '{name}'.")
            questions = questions.append(knext.Column(ktype, name))
        return questions

    def execute(self, ctx: knext.ExecutionContext, port: AirlockPortObject, questions: knext.Table | None) -> knext.Table:
        spec = port.spec
        client = ctx.get_credentials(spec.credentials)
        token = aisolate.sign_in(spec.token_url or aisolate.token_endpoint(spec.url), client.username, client.password)
        df = questions.to_pandas() if questions is not None else pd.DataFrame({"question": [self.question]})
        column = self.question_column if questions is not None else "question"
        rows = []
        for i, question in enumerate(df[column]):
            if ctx.is_canceled():
                raise RuntimeError("Canceled.")
            ctx.set_progress(i / max(len(df), 1), f"Asking question {i + 1} of {len(df)}")
            if not isinstance(question, str) or not question.strip():
                if self.missing_values == MissingValues.FAIL.name:
                    raise knext.InvalidParametersError(f"Row {i + 1} has no question.")
                rows.append({})
                continue
            rows.append(aisolate.answer_row(aisolate.ask(spec.url, spec.endpoint, token, question)))
        for name, key, ktype in _answer_columns(self.answer_column):
            # nullable dtypes: a row without a question gets missing values, and an empty table keeps the schema
            dtype = "Int64" if ktype == knext.int64() else "object"
            df[name] = pd.Series([row.get(key) for row in rows], index=df.index, dtype=dtype)
        return knext.Table.from_pandas(df)
