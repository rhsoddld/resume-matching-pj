# Mode Eval Subsets

Prepared subsets for shortest-path evaluation when lexical retrieval is already strong.

## hybrid

- queries: `16`
- family_mix: `backend`=4, `cloud_devops`=4, `data_analyst`=4, `frontend`=4
- `gs-q-002` `backend` recall@10=0.20 mrr=0.14 ndcg@5=0.00 must_have=0.80 first_rel_rank=7 top2_gap=0.0008
- `gs-q-003` `backend` recall@10=0.20 mrr=0.17 ndcg@5=0.00 must_have=0.60 first_rel_rank=6 top2_gap=0.0035
- `gs-q-011` `data_analyst` recall@10=0.20 mrr=0.33 ndcg@5=0.23 must_have=0.60 first_rel_rank=3 top2_gap=0.0052
- `gs-q-012` `data_analyst` recall@10=0.20 mrr=0.50 ndcg@5=0.12 must_have=0.40 first_rel_rank=2 top2_gap=0.0015
- `gs-q-001` `backend` recall@10=0.20 mrr=1.00 ndcg@5=0.20 must_have=0.60 first_rel_rank=1 top2_gap=0.0069
- `gs-q-015` `data_analyst` recall@10=0.40 mrr=0.11 ndcg@5=0.00 must_have=0.60 first_rel_rank=9 top2_gap=0.0107
- `gs-q-014` `data_analyst` recall@10=0.40 mrr=0.50 ndcg@5=0.29 must_have=0.60 first_rel_rank=2 top2_gap=0.0086
- `gs-q-004` `backend` recall@10=0.60 mrr=0.50 ndcg@5=0.12 must_have=0.80 first_rel_rank=2 top2_gap=0.0072
- `gs-q-008` `frontend` recall@10=0.60 mrr=0.50 ndcg@5=0.46 must_have=0.60 first_rel_rank=2 top2_gap=0.0
- `gs-q-007` `frontend` recall@10=0.60 mrr=1.00 ndcg@5=0.63 must_have=0.80 first_rel_rank=1 top2_gap=0.0018
- `gs-q-006` `frontend` recall@10=0.80 mrr=0.50 ndcg@5=0.67 must_have=0.60 first_rel_rank=2 top2_gap=0.0003
- `gs-q-017` `cloud_devops` recall@10=0.80 mrr=0.50 ndcg@5=0.36 must_have=1.00 first_rel_rank=2 top2_gap=0.0195
- `gs-q-009` `frontend` recall@10=0.80 mrr=1.00 ndcg@5=0.77 must_have=0.60 first_rel_rank=1 top2_gap=0.0075
- `gs-q-018` `cloud_devops` recall@10=0.80 mrr=1.00 ndcg@5=0.88 must_have=1.00 first_rel_rank=1 top2_gap=0.0124
- `gs-q-019` `cloud_devops` recall@10=0.80 mrr=1.00 ndcg@5=0.76 must_have=1.00 first_rel_rank=1 top2_gap=0.002
- `gs-q-020` `cloud_devops` recall@10=0.80 mrr=1.00 ndcg@5=0.65 must_have=1.00 first_rel_rank=1 top2_gap=0.0108

## rerank

- queries: `16`
- family_mix: `backend`=4, `cloud_devops`=4, `data_analyst`=4, `frontend`=4
- `gs-q-008` `frontend` recall@10=0.60 mrr=0.50 ndcg@5=0.46 must_have=0.60 first_rel_rank=2 top2_gap=0.0
- `gs-q-006` `frontend` recall@10=0.80 mrr=0.50 ndcg@5=0.67 must_have=0.60 first_rel_rank=2 top2_gap=0.0003
- `gs-q-002` `backend` recall@10=0.20 mrr=0.14 ndcg@5=0.00 must_have=0.80 first_rel_rank=7 top2_gap=0.0008
- `gs-q-012` `data_analyst` recall@10=0.20 mrr=0.50 ndcg@5=0.12 must_have=0.40 first_rel_rank=2 top2_gap=0.0015
- `gs-q-007` `frontend` recall@10=0.60 mrr=1.00 ndcg@5=0.63 must_have=0.80 first_rel_rank=1 top2_gap=0.0018
- `gs-q-019` `cloud_devops` recall@10=0.80 mrr=1.00 ndcg@5=0.76 must_have=1.00 first_rel_rank=1 top2_gap=0.002
- `gs-q-003` `backend` recall@10=0.20 mrr=0.17 ndcg@5=0.00 must_have=0.60 first_rel_rank=6 top2_gap=0.0035
- `gs-q-011` `data_analyst` recall@10=0.20 mrr=0.33 ndcg@5=0.23 must_have=0.60 first_rel_rank=3 top2_gap=0.0052
- `gs-q-001` `backend` recall@10=0.20 mrr=1.00 ndcg@5=0.20 must_have=0.60 first_rel_rank=1 top2_gap=0.0069
- `gs-q-004` `backend` recall@10=0.60 mrr=0.50 ndcg@5=0.12 must_have=0.80 first_rel_rank=2 top2_gap=0.0072
- `gs-q-009` `frontend` recall@10=0.80 mrr=1.00 ndcg@5=0.77 must_have=0.60 first_rel_rank=1 top2_gap=0.0075
- `gs-q-014` `data_analyst` recall@10=0.40 mrr=0.50 ndcg@5=0.29 must_have=0.60 first_rel_rank=2 top2_gap=0.0086
- `gs-q-015` `data_analyst` recall@10=0.40 mrr=0.11 ndcg@5=0.00 must_have=0.60 first_rel_rank=9 top2_gap=0.0107
- `gs-q-020` `cloud_devops` recall@10=0.80 mrr=1.00 ndcg@5=0.65 must_have=1.00 first_rel_rank=1 top2_gap=0.0108
- `gs-q-018` `cloud_devops` recall@10=0.80 mrr=1.00 ndcg@5=0.88 must_have=1.00 first_rel_rank=1 top2_gap=0.0124
- `gs-q-017` `cloud_devops` recall@10=0.80 mrr=0.50 ndcg@5=0.36 must_have=1.00 first_rel_rank=2 top2_gap=0.0195

## agent

- queries: `6`
- family_mix: `backend`=1, `cloud_devops`=2, `data_analyst`=1, `frontend`=2
- `gs-q-016` `cloud_devops` recall@10=1.00 mrr=1.00 ndcg@5=0.92 must_have=1.00 first_rel_rank=1 top2_gap=0.0232
- `gs-q-018` `cloud_devops` recall@10=0.80 mrr=1.00 ndcg@5=0.88 must_have=1.00 first_rel_rank=1 top2_gap=0.0124
- `gs-q-009` `frontend` recall@10=0.80 mrr=1.00 ndcg@5=0.77 must_have=0.60 first_rel_rank=1 top2_gap=0.0075
- `gs-q-010` `frontend` recall@10=0.80 mrr=1.00 ndcg@5=0.73 must_have=0.60 first_rel_rank=1 top2_gap=0.0122
- `gs-q-013` `data_analyst` recall@10=0.80 mrr=1.00 ndcg@5=0.59 must_have=0.60 first_rel_rank=1 top2_gap=0.0127
- `gs-q-005` `backend` recall@10=0.60 mrr=0.50 ndcg@5=0.36 must_have=0.80 first_rel_rank=2 top2_gap=0.0098
