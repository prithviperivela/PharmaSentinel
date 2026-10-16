-- 1. Corpus event mix: keep gold and predicted records separate.
SELECT p.split_name, e.record_kind, e.run_id, e.event_type,
       COUNT(*) AS event_count,
       COUNT(DISTINCT e.passage_id) AS passage_count,
       COUNT(DISTINCT p.source_group) AS source_group_count
FROM event_records e JOIN passages p ON p.passage_id = e.passage_id
GROUP BY p.split_name, e.record_kind, e.run_id, e.event_type;

-- 2. Annotation/extraction completeness by event type (empty text means empty role).
SELECT record_kind, run_id, event_type, COUNT(*) AS events,
       SUM(drug_text = '') AS absent_drug,
       SUM(effect_text = '') AS absent_effect,
       AVG(drug_text = '') AS absent_drug_fraction,
       AVG(effect_text = '') AS absent_effect_fraction
FROM event_records
GROUP BY record_kind, run_id, event_type;

-- 3. Exact text-bundle frequencies, not normalized medicine counts or incidence.
SELECT run_id, drug_text, effect_text, COUNT(*) AS event_count,
       COUNT(DISTINCT passage_id) AS passage_count,
       AVG(calibrated_confidence) AS mean_extraction_confidence
FROM event_records
WHERE record_kind = 'predicted' AND drug_text <> '' AND effect_text <> ''
GROUP BY run_id, drug_text, effect_text
ORDER BY event_count DESC;

-- 4. Expected number of incorrect emitted candidates per passage.
-- Missing events are not estimated by this query. Include no-output passages separately.
SELECT e.run_id, e.passage_id, COUNT(*) AS candidates,
       SUM(1 - e.calibrated_confidence) AS expected_incorrect_candidates,
       MIN(e.calibrated_confidence) AS weakest_candidate_confidence
FROM event_records e
WHERE e.record_kind = 'predicted'
GROUP BY e.run_id, e.passage_id
ORDER BY expected_incorrect_candidates DESC;

-- 5. Find evaluated passages with no predicted event, including potential misses.
SELECT r.run_id, p.passage_id, p.source_group, p.split_name
FROM passages p CROSS JOIN experiment_runs r
WHERE r.model_type <> 'gold_annotation'
  AND p.annotation_status = 'valid'
  AND JSON_UNQUOTE(JSON_EXTRACT(r.metrics_json, '$.split')) = p.split_name
  AND NOT EXISTS (
    SELECT 1 FROM event_records e
    WHERE e.passage_id = p.passage_id AND e.record_kind = 'predicted'
      AND e.run_id = r.run_id
);

