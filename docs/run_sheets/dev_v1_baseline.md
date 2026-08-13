# Dev v1 baseline run sheet

## Provenance metadata (do not paste into the generation model)

- Evaluation run ID: `1`
- Comparison group: `DEV-COMP-01`
- Split: `dev`
- Prompt version ID: `1` (frozen Prompt v1)
- Grader condition ID: `1` (owner-approved v1 snapshots)
- Generator product: `ChatGPT web UI (manual)`
- Generator visible model: `not_visible`
- Protocol version: `manual-generation-v1`
- Run created at: `2026-08-13T13:39:44.763253Z`
- Dev-only case-set hash: `a23f8d88ad1e35443d3b31bfcd0c60274b204cdbd0738d4ab21eefd24db3cb1c`
- Task Pack contract hash: `ae273822b78d16cba4df5d784d611313f788353229d1b95166047cc1254a2c59`
- Generation packet version: `generation-1.0`

This run sheet and the JSON manifest are provenance records. Only the contents
of a packet file are model-facing. Do not paste this run sheet, the manifest,
or any IDs/hashes into ChatGPT.

## Required manual protocol

1. Use the ChatGPT web UI for every Case in this run.
2. Before starting, open **Model Outputs** and select this Evaluation Run. In
   **Confirm generator condition before capture**, record the exact visible
   model name if the UI shows one; otherwise confirm `not_visible`. Do not
   capture the first response until this condition has been recorded. If a
   model is visible, use that same exact model for all 18 Cases; never infer a
   name when it is not visible.
3. For every Case, open a clean, new conversation. Do not reuse a thread.
4. Open exactly one listed packet file and paste its complete model-facing
   text unchanged into that fresh conversation.
5. Capture the first actual response verbatim, including malformed JSON,
   extra prose, or any quality failure. In the app, select this Evaluation Run
   and Case on **Model Outputs**, paste the raw response into **Record first
   actual response**, retain the actual UTC timestamp, and submit. The app
   then records deterministic Rule Checks.
6. Never retry for output quality. Do not ask follow-up questions, request a
   correction, edit the response, repair JSON, or reformat it before capture.
7. A retry is permitted only for a page/load/network/no-response technical
   failure. In that case, use **Record technical retry** in the app before
   trying again and record the concrete reason. It increments the retry count
   without creating an output-quality result.
8. Work through all 18 Dev Cases in one reasonably short execution window.
   Do not open, render, or use any Holdout Case during this phase.

## Packet hash index

- `brief-dev-01` — `docs/run_sheets/dev_v1_packets/brief-dev-01.txt` — `d9080942bc70c5144eb2591fdc446990fe3b66f101b5d26ddea167e4ef2e6a68`
- `brief-dev-02` — `docs/run_sheets/dev_v1_packets/brief-dev-02.txt` — `918a83767d853623e9836b6964af7bca272f1688e2cdfafd172a63ad49fd6a1a`
- `brief-dev-03` — `docs/run_sheets/dev_v1_packets/brief-dev-03.txt` — `f8236c2aa7bcb4b6c05bcacae33134a149f2c452902f45003e238ac4991eae18`
- `brief-dev-04` — `docs/run_sheets/dev_v1_packets/brief-dev-04.txt` — `2113e0757d5f9d1ebab1a10b52a7e2381cb6f81b1187552b4ee3de9997379ff0`
- `brief-dev-05` — `docs/run_sheets/dev_v1_packets/brief-dev-05.txt` — `9859b4e75954ea098d6fe9b728605e16237d544c41094e60fa4da7a9de593af7`
- `brief-dev-06` — `docs/run_sheets/dev_v1_packets/brief-dev-06.txt` — `b1e639c31dc890e7a2f464a1e623caf224d022387e43ab164d7b93c7b787c7b8`
- `brief-dev-07` — `docs/run_sheets/dev_v1_packets/brief-dev-07.txt` — `46c5d64209d080712e3da74e8e2e4d88ea6685aa129ae1257c264a000e31011a`
- `brief-dev-08` — `docs/run_sheets/dev_v1_packets/brief-dev-08.txt` — `ad10995dea2e1c434fce5a0407fb6f4e11d31f8f2571a0a0167f0dd8791ed797`
- `brief-dev-09` — `docs/run_sheets/dev_v1_packets/brief-dev-09.txt` — `8ec19a0afa8eb7c4da65e526f8f2149d77a7d1c667bb795230624b0b0187f7bc`
- `brief-dev-10` — `docs/run_sheets/dev_v1_packets/brief-dev-10.txt` — `7e8a3cb49e561f4d871d9fc4c5403e072a5ae567bc57a12272119fc8c1bbb1ec`
- `brief-dev-11` — `docs/run_sheets/dev_v1_packets/brief-dev-11.txt` — `9296d6f9ece3ca20d21c7798a6b77e92922f6991d3c83e5b18cb5f70c7d803c2`
- `brief-dev-12` — `docs/run_sheets/dev_v1_packets/brief-dev-12.txt` — `2335172c10366cd873107a2447003a67de96b9a9d6ba86913bba8dd81baa08a0`
- `brief-dev-13` — `docs/run_sheets/dev_v1_packets/brief-dev-13.txt` — `289128efbf0a869dd57bf6d90e2b5eb0228899758a7a310eb95f93eca84640f8`
- `brief-dev-14` — `docs/run_sheets/dev_v1_packets/brief-dev-14.txt` — `23ee9ca8ce59ef7388bcc88b0650a77d1ba26046e7bbb06c56c04e612c688af4`
- `brief-dev-15` — `docs/run_sheets/dev_v1_packets/brief-dev-15.txt` — `8bd351b1180d8a9b6ac5c3466a440a17dfdddafbb2c6a3c826a379a84e0c2e29`
- `brief-dev-16` — `docs/run_sheets/dev_v1_packets/brief-dev-16.txt` — `295b70e93f46543be79a5479dd9e91b0924fde981c1363100e43be676fc8d475`
- `brief-dev-17` — `docs/run_sheets/dev_v1_packets/brief-dev-17.txt` — `f8ff0ad82ea8fcc46d6094f6393f93242df40b5f621670a02e717241ba049820`
- `brief-dev-18` — `docs/run_sheets/dev_v1_packets/brief-dev-18.txt` — `0f104de28473ddce40b7202efaa6f2401a079459ebc832c1fbce084748326316`
