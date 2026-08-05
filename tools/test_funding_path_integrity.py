from __future__ import annotations

from validate_funding_path_integrity import validate


def fixture():
    def common(path_id, kind, decision="REJECTED"):
        return {
            "path_id": path_id, "kind": kind, "decision": decision,
            "reset_rule": "命中后回基础档", "cap_rule": "达到上限后停止",
            "selection_reason": "完成同口径资金对照",
        }
    flat = common("FLAT", "FLAT", "SELECTED"); flat["sequence"] = [1] * 10
    linear = common("LIMITED_LINEAR", "LIMITED_LINEAR"); linear["sequence"] = [1,1,2,2,3,3]
    pressure = common("PRESSURE_RELEASE", "PRESSURE_RELEASE")
    pressure.update(sequence=[1,1,2,2,3,2,1,1,2,1,1], cycle_mode="STOP_AT_END")
    advanced = common("ADVANCED_STATE", "ADVANCED_STATE")
    advanced.update(
        states=["BASE","BUILD","RELEASE","STOP"],
        transitions=[
            {"from":"BASE","on":"WIN","to":"BASE"},
            {"from":"BASE","on":"LOSS","to":"BUILD"},
            {"from":"BUILD","on":"WIN","to":"RELEASE"},
            {"from":"BUILD","on":"LOSS","to":"RELEASE"},
            {"from":"RELEASE","on":"CAP","to":"STOP"},
        ],
        partial_recovery_rule="命中但净值仍为负时只降压，不宣称回本",
    )
    stress=[]
    for n in [10,20,30,40,50]:
        stress.append({
            "loss_streak":n,"cumulative_investment":n*0.5,"remaining_capital":5000-n*0.5,
            "next_multiplier":1,"next_investment":0.5,"net_after_next_hit":-(n*0.5)+0.35,
            "full_recovery":False,"can_continue":True,
        })
    return {
        "schema_version":1,"run_id":"TEST","capital_base":5000,"minimum_unit":0.1,
        "single_period_cost_at_1x":0.5,"gross_return_at_1x":0.85,"theoretical_hit_rate":0.5,
        "historical_periods":200,"data_maturity":"QUICK_EXPERIMENT_ONLY","claims":["仅流程验证"],
        "funding_paths":[flat,linear,pressure,advanced],"stress_checkpoints":stress,
        "random_simulation":{"paths":10000,"model":"THEORETICAL_BERNOULLI","periods_per_path":200},
    }


def durable_fixture():
    data=fixture()
    data.update(
        long_horizon_requested=True,
        durability_definition="限制最大倍数并在极端连挂后转入1倍尾仓，不承诺回本",
        durability_cap_multiplier=3,
    )
    data["funding_paths"][0]["decision"]="REJECTED"
    adv=data["funding_paths"][3]
    adv["decision"]="SELECTED"
    states=[f"S{i}" for i in range(1,25)]
    mult=[1]*8+[2]*6+[3]*4+[2,2,1,1]+[1,1]
    transitions=[]
    for i,state in enumerate(states):
        loss=states[min(i+1,23)]
        transitions.append({"from":state,"on":"LOSS","to":loss})
        transitions.append({"from":state,"on":"WIN","to":"S1" if i<8 or i>=22 else states[max(0,i-6)]})
    transitions.append({"from":"S24","on":"CAP","to":"S24"})
    adv.update(
        states=states,state_multipliers=mult,transitions=transitions,tail_policy="HOLD_LAST_1X",
        partial_recovery_rule="命中只按状态退档；净值为负时不得标记完全回本",
    )
    return data


def run_tests():
    good=fixture(); assert not validate(good), validate(good)
    repeated=fixture(); repeated["funding_paths"][2]["sequence"]=[1,1,2,2,3,3,5,5,3,2,1,1]*5; repeated["funding_paths"][2]["cycle_mode"]="REPEAT"
    errors=validate(repeated); assert any("机械重复" in e for e in errors); assert any("不得无限循环" in e for e in errors)
    fake_state=fixture(); fake_state["funding_paths"][3]["transitions"]=["BASE->BUILD","BUILD->BASE"]
    assert any("结构化转移" in e or "from/on/to" in e for e in validate(fake_state))
    missing=fixture(); missing["stress_checkpoints"]=missing["stress_checkpoints"][:-1]
    assert any("10/20/30/40/50" in e for e in validate(missing))
    few=fixture(); few["random_simulation"]["paths"]=9999; assert any("至少10000" in e for e in validate(few))
    claim=fixture(); claim["claims"]=["稳定盈利"]; assert any("禁止声称" in e for e in validate(claim))

    fake_long=fixture(); fake_long.update(long_horizon_requested=True,durability_definition="长期抗造",durability_cap_multiplier=3)
    fake_long["funding_paths"][0]["sequence"]=[1]*60
    errors=validate(fake_long); assert any("有效深度仍为1" in e for e in errors)

    short_adv=durable_fixture(); short_adv["funding_paths"][3]["states"]=short_adv["funding_paths"][3]["states"][:6]
    short_adv["funding_paths"][3]["state_multipliers"]=short_adv["funding_paths"][3]["state_multipliers"][:6]
    errors=validate(short_adv); assert any("至少18个状态" in e for e in errors)

    loop_tail=durable_fixture(); loop_tail["funding_paths"][3]["transitions"][-2]={"from":"S24","on":"LOSS","to":"S1"}
    errors=validate(loop_tail); assert any("最后状态LOSS必须自锁" in e for e in errors)

    durable=durable_fixture(); assert not validate(durable), validate(durable)


if __name__ == "__main__":
    run_tests(); print("funding path integrity tests: PASS")
