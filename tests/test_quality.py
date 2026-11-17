from tse.eval.run import settings
from tse.product.qa import check

CFG = settings()


class Model:
    def __init__(self, followed, conf):
        self.v = {"followed": followed, "confidence": conf}

    def judge(self, call_id, text, g):
        return self.v


def call(*lines):
    return {"id": "c1", "text": "\n".join(lines)}


def test_rules_read_only_what_the_agent_said():
    c = call("customer: Hello, my name is Kim speaking.", "agent: One moment please.")
    f = {x.guideline: x for x in check(c, ["greeting"], Model(True, 0.99), CFG)}
    assert f["greeting"].followed is False


def test_a_hedge_that_names_a_promise_goes_to_a_person():
    c = call("agent: I cannot promise a date, but I will escalate this today.",
             "customer: Can you promise me it won't happen again?")
    f = check(c, ["no_promise"], Model(True, 0.97), CFG)[0]
    assert f.followed is None and f.by == "review"


def test_the_model_decides_only_when_sure():
    c = call("agent: Thank you for your patience.")
    assert check(c, ["no_promise"], Model(True, 0.95), CFG)[0].followed is True
    assert check(c, ["no_promise"], Model(True, 0.6), CFG)[0].followed is None
    assert check(c, ["no_promise"], Model(False, 0.95), CFG)[0].followed is False
