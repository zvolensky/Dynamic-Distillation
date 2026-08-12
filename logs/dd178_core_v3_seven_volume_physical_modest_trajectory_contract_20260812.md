# DD-178 Seven-Volume Physical-Policy Modest-Trajectory Contract

- Payload SHA-256: `98213b091747864ea3f6e73f9edf9d77cab2779995a33ef5540c2899619466b6`
- Preparation base commit: `37ff0fc88f19784bb52cc80ee735ef7aef41cc96`
- Disturbance: unchanged DD-177 open-loop feed step
- Duration: `10.0 s`
- Coarse path: `40 x 0.25 s`
- Refined path: `80 x 0.125 s`
- Shared-time comparisons: `40`
- Evidence: compact per-root scalars plus complete endpoints
- Legacy unfloored component ratio: diagnostic only
- Controllers: disabled

Commit before the one execution. Retry, alternate grid, controller, projection, clipping, fallback, or continuation is prohibited.
