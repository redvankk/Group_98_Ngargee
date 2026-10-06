# Club data

| File | What it is | Edit it? |
|---|---|---|
| `Clubs.csv` | Team's manual spreadsheet (Windows-1252 encoding; some rows have event columns shifted) | Yes, source |
| `../scraper/club_profiles_structured.csv` | Rubric scrape: every club, its Rubric page and scrape date | Re-run the scraper |
| `five_clubs/` | Team's detailed files for CSIT, RISC, REECE, Matrix and SWITCH: `club.csv`, `membership.csv`, `social.csv`, `executive.csv` | Yes, source |
| `build_dataset.py` | Merges the two sources into the tidy files below | Only to change merge rules |
| **`clubs_master.csv`** | One clean row per club, UTF-8. **The app's knowledge base.** | No, rebuild it |
| `collection.csv` / `collection.jsonl` | One passage per club in Walert's format (`passage_id,passage` / `{"id","contents"}`), for Pyserini or Walert's scripts | No, rebuild it |
| `build_report.csv` | How each club was matched between sources, and which rows had event columns realigned | Check after a rebuild |
| `club_aliases.csv` (optional) | Extra names for clubs: columns `club,alias` | Yes |

Rebuild after changing a source: `python data/build_dataset.py` (from `backend/`).

## `clubs_master.csv` columns

| Column | Notes |
|---|---|
| `club_id` | Stable id from the name; used in `eval/qrels.txt` and run files |
| `name`, `category` | Category is one of the five Rubric categories |
| `tags` | The team's finer-grained category, e.g. "Academic / Astronomy / Science" |
| `description`, `description_quality` | Longest real description from either source. `placeholder` = only Rubric's "Hello from…" greeting; the app treats these as having no description |
| `who_can_join`, `campus` | From the team spreadsheet |
| `email`, `instagram`, `facebook`, `discord`, `linkedin`, `website`, `join_url` | Links prefer real URLs from either source |
| `rubric_url` | The club's Rubric page; used as the citation link |
| `event_name`, `event_date`, `event_location`, `event_type`, `event_frequency` | As listed when checked; the assistant only calls an event upcoming if its date is after today |
| `notes` | Past activities, membership notes, extra contacts |
| `events_checked` | When the team checked the event details |
| `sources`, `last_checked` | Where the row came from, and the most recent check or scrape date |
| `acronym`, `also_known_as` | Five computing clubs: acronym and other names (all work as search aliases) |
| `focus_area` | `Computing` for the five computing clubs; "computing clubs" questions return all five |
| `membership_full`, `membership_associate`, `membership_social`, `membership_under_18` | Membership tiers and eligibility, from `five_clubs/membership.csv` |
| `linktree` | From `five_clubs/social.csv`, whose links override other sources for these clubs |
| `committee` | Committee names and roles from `five_clubs/executive.csv`. **Includes students' names; the team is still deciding whether to keep this** |

For the five computing clubs, the name used is the best match across sources: the
one containing the acronym (e.g. "SWITCH (Society of Women in Technology)"),
otherwise the longest (e.g. "RMIT Information Security Collective"). Club ids
stay the same so the evaluation files still match.

## Evaluation files (`../eval/`)

`topics.csv` (`topic_id, topic, question_type, difficulty, question_id, question`) and
`qrels.txt` (`question_id 0 club_id relevance`, tab-separated) follow Walert's
layout. 50 questions, one per topic: 15 easy (E01–E15), 28 hard (H01–H28: comparisons,
eligibility edge cases, event dates, lists, paraphrases with no club keywords, typos,
fairness) and 7 unanswerable (U01–U07). Several come from the team's `team_queries.csv`;
`reference_answers.csv` holds the team's written answers (used for ROUGE-L). The earlier
75-question set is kept as `topics_v1_75q.csv` / `qrels_v1_75q.txt`.
Relevance: 2 = answers the question, 1 = partly relevant. `U` topics are
unanswerable and have no qrels; the assistant should decline them. This set is a
**draft for the team to review**: check each judgement against the data.
