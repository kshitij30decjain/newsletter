import json

from github_discovery import GitHubRepoDiscovery



def main():

    # Create GitHub discovery object
    github_discovery = GitHubRepoDiscovery(
        database_path="github_growth.db",
        top_n=8,
        snapshot_window_days=30,
        search_pages=2
    )

    # Run discovery
    result = github_discovery.run()

    # --------------------------------------------------
    # Print complete result
    # --------------------------------------------------

    print("\n")
    print("=" * 80)
    print("FINAL RESULT")
    print("=" * 80)

    print(
        json.dumps(
            result,
            indent=4
        )
    )

    # --------------------------------------------------
    # Get repositories
    # --------------------------------------------------

    repos = result.get("tags", [])

    print("\n")
    print("=" * 80)
    print("TOP GITHUB REPOSITORIES")
    print("=" * 80)

    if not repos:

        print(
            "\nNo 30-day growth results yet."
        )

        print(
            "This is expected on the first run."
        )

        print(
            "The script is collecting the baseline "
            "stars/forks data."
        )

    else:

        for index, repo in enumerate(
            repos,
            start=1
        ):

            print(
                f"\n{index}. {repo['repo']}"
            )

            print(
                f"   Stars: "
                f"{repo['stars']:,}"
            )

            print(
                f"   Forks: "
                f"{repo['forks']:,}"
            )

            print(
                f"   Star growth (30d): "
                f"+{repo['star_growth_30d']:,}"
            )

            print(
                f"   Fork growth (30d): "
                f"+{repo['fork_growth_30d']:,}"
            )

            print(
                f"   Star growth %: "
                f"{repo['star_growth_pct']}%"
            )

            print(
                f"   Fork growth %: "
                f"{repo['fork_growth_pct']}%"
            )

            print(
                f"   Growth score: "
                f"{repo['growth_score']}"
            )

            print(
                f"   URL: "
                f"{repo['url']}"
            )


if __name__ == "__main__":
    main()
