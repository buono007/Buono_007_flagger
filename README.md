# Buono_007_flagger

A local-first toolkit to download challenge metadata and files from a CTF platform, then submit flags from command line with profile-aware authentication and per-challenge routing.

This project has been developed with ideas inspired in part by mjouins/sCCraper-IT.

## Attribution

Part of the scraper-oriented idea and workflow inspiration comes from mjouins/sCCraper-IT.

## What this project does

This repository provides two main command-line workflows:

1. Scraping workflow
- Connects to a challenge platform API.
- Authenticates with profile credentials.
- Downloads challenge trees, challenge detail metadata, optional hints, and files.
- Saves data on disk with a normalized folder structure.
- Supports selective updates, event/section filtering, challenge id filtering, and concurrent downloads.

2. Flag submission workflow
- Reads a flag from argument or piped command output.
- Detects or normalizes flag format.
- Reads challenge JSON when available to get challenge id, submit link, and profile name.
- Logs in with selected profile credentials.
- Submits the flag to the platform API endpoint.
- Tracks sent flags in challenge JSON.
- Displays a visual celebration path when enabled.

## Project files and responsibilities

- [main.py](main.py)
: Entry point for scraping challenges.

- [flag.py](flag.py)
: Entry point for flag extraction/normalization/submission and local sent-flag tracking.

- [config.py](config.py)
: Profile and active-profile resolution, environment fallback, profile persistence helpers.

- [session.py](session.py)
: HTTP session, API login, retry strategy, rate limiting, token cache reuse and refresh.

- [scraper.py](scraper.py)
: High-level scrape orchestration, challenge processing, hints/files retrieval, concurrent workers.

- [utils.py](utils.py)
: Filesystem and JSON utilities, filename normalization, manifest-based update tracking.

- [set_active_profile.py](set_active_profile.py)
: Utility CLI to inspect and change the active profile used by default mode.

- [profiles.json](profiles.json)
: Profile map for BASE_URL, EMAIL, PASSWORD entries.

- [active_profile.json](active_profile.json)
: Stores which profile name is currently active.

- [.token_cache.json](.token_cache.json)
: Local runtime cache for tokens and files tokens used for session reuse.

## Runtime model

### Profile model

Configuration can come from:

1. Explicit profile name passed in CLI.
2. Default profile mode which resolves through active profile selection.
3. Environment fallback when profile default is requested and no valid profile entry exists.

For default behavior:
- The active profile name is read from active_profile.json.
- If that name exists in profiles.json, that profile is used.
- If there is a profile literally named default, that profile can also be used.
- If exactly one profile exists, it is used as implicit default.
- If multiple profiles exist and active profile is invalid, an explicit error is raised.

### Session model

Session uses:
- Retry strategy for transient server errors.
- Rate limit delay between requests.
- Token auth header for API endpoints.
- Files token for file endpoint auth query string.
- Token cache for reuse across runs.

Token cache key identity is composed from:
- Profile name
- Base URL
- Email

On startup:
1. Try cached token entry.
2. Validate token by calling currentUser.
3. If valid, reuse token.
4. If invalid or expired, perform fresh login and update cache.

### Challenge storage model

For each challenge, metadata JSON is saved in a deterministic folder path:

Data directory
- data/challenges/{event}/{section}/{title}/

Challenge metadata includes saved values from API plus local additions:
- link
: The base URL used during download.
- profile
: The profile name used during download.

A manifest file tracks downloaded challenge ids for update-only mode.

## Command-line flows

### Scraping

Typical behavior of the scraping command:

1. Parse CLI arguments.
2. Resolve configuration from profile logic.
3. Create Session with retry, rate limiting, and token cache logic.
4. Download challenge tree endpoint and save it.
5. Filter and process selected challenges.
6. Save challenge metadata and download attached files.
7. Mark processed challenges in manifest.
8. Print summary stats.

Scrape filters supported:
- events
- sections
- challenge ids
- update-only mode
- max worker count

### Flag submission

Typical behavior of the flag command:

1. Read flag from positional argument or from piped stdin.
2. When piped, mirror stdin output in real time while collecting text.
3. Extract/normalize flag candidate.
4. Discover challenge JSON from explicit path or current directory scan.
5. Resolve profile from CLI, then override from challenge profile when available.
6. Resolve base URL from CLI, challenge link, then profile config.
7. Create Session and authenticate.
8. Resolve challenge id from CLI override or challenge JSON id.
9. Submit flag to API route.
10. Print response state and visual output.
11. Update SENT_FLAGS in challenge JSON.

## Detailed function reference

## main.py

Function: main

Responsibilities:
- Defines scraping CLI interface and options.
- Resolves profile configuration through get_config.
- Creates a session with profile-aware cache keying.
- Calls fetch_and_save_challenges.
- Calls scrape_all with filters and worker settings.
- Logs success/failure states.

Inputs:
- profile
- update-only
- events
- sections
- challenge-ids
- max-workers
- rate-limit

Output:
- Side effects on filesystem data folder and network calls.
- Logging to console.

## config.py

Function: load_profiles
- Reads profiles.json and returns parsed dictionary.
- Returns empty dictionary if file missing or invalid.

Function: get_active_profile_name
- Reads active_profile.json.
- Returns active profile string or default fallback.

Function: set_active_profile
- Writes active profile choice to active_profile.json.

Function: get_config
- Main profile resolver.
- Accepts profile name, supports default resolution strategy.
- Returns BASE_URL, EMAIL, PASSWORD map.
- Raises explicit ValueError on invalid multi-profile default state.

Function: save_profile
- Adds or updates one profile entry in profiles.json.
- Persists profile details with indentation.

## session.py

Class: ColoredFormatter

Method: format
- Applies color mapping based on logging level.
- Returns formatted logging string.

Function: _configure_logger
- Adds one stream handler with colored formatter.
- Prevents duplicate handlers across repeated imports.

Class: Session

Method: __init__
- Stores base_url/email/profile_name.
- Builds requests session.
- Applies retry adapters.
- Attempts token restore from cache.
- Falls back to fresh login when needed.

Method: _cache_key
- Creates stable cache key string from profile and identity dimensions.

Method: _load_token_cache
- Reads .token_cache.json.
- Returns dictionary or empty dictionary.

Method: _save_token_cache
- Writes token cache dictionary to disk.

Method: _store_tokens
- Sets in-memory auth header token and file token query fragment.

Method: _try_restore_tokens
- Loads cached token for cache key.
- Applies token.
- Validates token by calling currentUser.
- Returns True on success, False on invalid/expired token.

Method: _save_current_tokens
- Persists token/filesToken plus updated timestamp.

Method: _apply_rate_limit
- Enforces minimum delay between API requests.

Method: _login
- Calls API login endpoint using email/password payload.
- Extracts token and filesToken.
- Stores and persists tokens.
- Loads current user and group.

Method: api_get
- Performs authenticated API GET call.
- Applies rate limit and raises on HTTP failures.

Method: download_file
- Downloads file stream with optional resume header.
- Uses file token query parameter fragment.
- Writes in append or write mode based on existing partial file.

## scraper.py

Class: _NoOpProgressBar
- Simple fallback progress object used when tqdm is unavailable.

Function: get_progress_bar
- Tries to load tqdm dynamically.
- Returns tqdm progress bar or no-op fallback.

Function: reset_stats
- Resets global summary counters.

Function: fetch_and_save_challenges
- Calls challenges API tree endpoint.
- Saves response to data/challenges.json.

Function: fetch_challenge_data
- Calls challenge detail endpoint by id.

Function: fetch_challenge_hints
- Iterates hint ids and fetches hint detail one by one.

Function: download_file_safe
- Downloads one file.
- If zip, extracts to dedicated subfolder.
- Uses 7z when available, otherwise built-in zipfile extraction.
- Returns boolean result instead of raising.

Function: process_challenge
- Applies update-only skip logic.
- Builds challenge directory path.
- Fetches challenge detail and enriches local fields.
- Saves challenge metadata JSON.
- Downloads attached files concurrently.
- Marks challenge as downloaded in manifest.
- Captures errors and returns status.

Function: scrape_all
- Builds filtered list of challenges across events/sections.
- Runs concurrent challenge processing with worker pool.
- Updates success/failure counters.
- Displays scrape summary.

## utils.py

Function: clean_filename
- Converts title to filesystem-safe token by replacing spaces and stripping unsupported characters.

Function: get_data_dir
- Returns root data directory path.

Function: get_challenge_dir
- Returns full directory path for one challenge based on event/section/title.

Function: ensure_dir
- Creates directory if missing.

Function: save_json
- Writes dictionary to JSON with indentation.

Function: load_json
- Reads JSON file to dictionary or returns empty dictionary if missing.

Function: load_manifest
- Reads manifest JSON from data directory.

Function: save_manifest
- Writes manifest JSON to data directory.

Function: is_challenge_downloaded
- Checks manifest membership only when update-only mode is active.

Function: mark_challenge_downloaded
- Stores timestamp for challenge id in manifest.

## flag.py

Function: cprint
- Prints colored messages with immediate flush.

Function: read_stdin_realtime
- Reads stdin line by line.
- Mirrors each line to stdout in real time.
- Returns collected text buffer.

Function: discover_challenge_config
- Resolves challenge JSON from explicit path or first compatible JSON in current folder.
- Validates required challenge keys.

Class: FlagSubmitter

Method: __init__
- Stores session, base URL, response verbosity and celebration toggle.

Method: _is_challenge_json
- Verifies minimal challenge schema keys.

Method: find_challenge_config
- Delegates challenge discovery to discover_challenge_config.

Method: update_sent_flags
- Appends submitted flag to SENT_FLAGS if not already present.
- Persists challenge JSON update.

Method: submit_flag
- Calls API submit endpoint for challenge id.

Method: celebrate
- Draws full-screen terminal-style success scene with centered ASCII art and flag text.

Method: run
- Resolves challenge id from override or challenge JSON.
- Skips already-sent flags.
- Resolves submit base URL from challenge link or session base URL.
- Sends submit request.
- Prints success/failure output.
- Applies visible failure banner when celebration mode is enabled.
- Updates SENT_FLAGS on local challenge JSON.

Function: extract_flag
- Extracts flag-like token from arbitrary text via regex.
- Supports flag and CCIT style wrappers.

Function: normalize_flag
- Produces final flag text with optional wrapper auto-insertion.

Function: parse_args
- Defines CLI options for profile, challenge selection, base URL override, output and celebration behavior.

Function: main
- Orchestrates input reading, challenge discovery, profile selection, config resolution, session creation, and submission run.
- Uses challenge profile and link as runtime overrides when present.

## set_active_profile.py

Function: parse_args
- Defines profile activation CLI options.

Function: main
- Loads profiles.
- Prints active and available profiles with show mode.
- Accepts explicit or interactive profile choice.
- Validates profile exists.
- Persists active profile selection.

## Data files and generated artifacts

### profiles.json
- Stores named profile credentials and base URLs.

### active_profile.json
- Stores active profile pointer used by default mode.

### data folder
- Contains challenge tree export, challenge metadata, downloaded files, and manifest.

### .token_cache.json
- Stores cached API token and files token by profile/base_url/email key.

## Practical behavior notes

1. Profile override precedence in flag submit flow
- CLI profile is initial profile choice.
- If challenge JSON has profile field, that value is used as selected profile.

2. Base URL precedence in flag submit flow
- Explicit base URL argument first.
- Challenge JSON link second.
- Profile BASE_URL last.

3. Authentication payload format
- Login uses email and password fields in JSON payload.

4. Challenge JSON discovery
- Explicit path wins.
- Otherwise first JSON in working directory that has id and title is selected.

5. update-only behavior
- Uses manifest membership only.
- If challenge id already in manifest, challenge is skipped.

## Security and publishing notes

This project can store sensitive runtime artifacts locally:
- profile credentials in profiles.json
- API tokens in .token_cache.json

If publishing publicly:
- avoid committing local credential files
- avoid committing token cache files
- avoid logging secrets in production environments

## Example usage

Scrape everything with active/default profile
- python main.py

Scrape only new content
- python main.py --update-only

Scrape selected events
- python main.py --events EventOne EventTwo

Scrape selected sections
- python main.py --sections SectionA SectionB

Scrape selected challenge ids
- python main.py --challenge-ids 1 2 3

Submit a direct flag
- python flag.py flag{example}

Submit by piping output from another command
- python some_script.py | python flag.py

Submit with explicit challenge file
- python flag.py flag{example} --challenge-file path/to/challenge.json

Show active profile and available profiles
- python set_active_profile.py --show

Set active profile
- python set_active_profile.py test

## Credits

- Project author: Buono_007 maintainer.
- Partial conceptual inspiration for scraper workflow: mjouins/sCCraper-IT.
