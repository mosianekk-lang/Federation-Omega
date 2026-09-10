from aegis_omega.adversarial.twin import scenario_suite
from aegis_omega.adversarial.neural_sentinel import NeuralSentinel, feature_vector
def _data():
    rows=[]
    for case in scenario_suite(): rows.extend([(feature_vector(case.events),1 if case.expected_threat_like else 0)]*2)
    return rows
def test_neural_sentinel_is_shadow_only_and_deterministic():
    data=_data(); model1,r1=NeuralSentinel.train_synthetic_shadow(data[:16],data[16:]); model2,r2=NeuralSentinel.train_synthetic_shadow(data[:16],data[16:]); assert r1.shadow_only and r1.synthetic_training_only; assert r1.model_sha256==r2.model_sha256==model1.model_hash()==model2.model_hash()
def test_neural_sentinel_outputs_probability():
    model=NeuralSentinel(); p=model.predict(feature_vector(scenario_suite()[0].events)); assert 0.0<=p<=1.0
