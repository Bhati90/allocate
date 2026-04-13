#!/usr/bin/env python3
"""
Tender Dashboard — New Relic Dashboard Creator

Creates 3 monitoring dashboards via the NerdGraph API.

Usage:
    1. Get your User API key from https://one.newrelic.com/api-keys
       (Type: USER, starts with NRAK-)
    2. Run:
       python create_dashboards.py NRAK-YOUR-USER-API-KEY-HERE

    That's it. Three dashboards will appear in your New Relic account.
"""

import sys
import json
import urllib.request

ACCOUNT_ID = 7933695
NERDGRAPH_URL = "https://api.newrelic.com/graphql"


def create_dashboard(api_key, dashboard_config):
    """Create a single dashboard via NerdGraph mutation."""

    # Build the GraphQL mutation
    mutation = """
    mutation($accountId: Int!, $dashboard: DashboardInput!) {
        dashboardCreate(accountId: $accountId, dashboard: $dashboard) {
            entityResult {
                guid
                name
            }
            errors {
                type
                description
            }
        }
    }
    """

    payload = json.dumps({
        "query": mutation,
        "variables": {
            "accountId": ACCOUNT_ID,
            "dashboard": dashboard_config
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        NERDGRAPH_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "API-Key": api_key,
        },
    )

    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode())

    errors = result.get("data", {}).get("dashboardCreate", {}).get("errors", [])
    entity = result.get("data", {}).get("dashboardCreate", {}).get("entityResult")

    if errors:
        print(f"  ❌ Errors: {errors}")
        return None
    elif entity:
        print(f"  ✅ Created: {entity['name']}")
        print(f"     GUID: {entity['guid']}")
        return entity['guid']
    else:
        print(f"  ❌ Unexpected response: {json.dumps(result, indent=2)}")
        return None


# ====================================================================
# DASHBOARD 1: Health at a Glance
# ====================================================================
DASHBOARD_1 = {
    "name": "Tender \u2014 Health at a Glance",
    "description": "Morning check: traffic-light billboards, error trends, API health",
    "permissions": "PUBLIC_READ_WRITE",
    "pages": [
        {
            "name": "Health Overview",
            "widgets": [
                {
                    "title": "\ud83d\udd34 Errors (Last 1 Hour)",
                    "visualization": {
                        "id": "viz.billboard"
                    },
                    "layout": {
                        "column": 1,
                        "row": 1,
                        "height": 3,
                        "width": 3
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT count(*) AS 'Errors' FROM TransactionError WHERE appName = 'tender' SINCE 1 hour ago"
                            }
                        ],
                        "thresholds": [
                            {
                                "alertSeverity": "WARNING",
                                "value": 1
                            },
                            {
                                "alertSeverity": "CRITICAL",
                                "value": 5
                            }
                        ]
                    }
                },
                {
                    "title": "\u2705 Webhook Success Rate",
                    "visualization": {
                        "id": "viz.billboard"
                    },
                    "layout": {
                        "column": 4,
                        "row": 1,
                        "height": 3,
                        "width": 3
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT percentage(count(*), WHERE httpResponseCode < 400) AS 'Webhook OK %' FROM Transaction WHERE appName = 'tender' AND name LIKE '%webhook%' SINCE 1 hour ago"
                            }
                        ],
                        "thresholds": [
                            {
                                "alertSeverity": "WARNING",
                                "value": 98
                            },
                            {
                                "alertSeverity": "CRITICAL",
                                "value": 95
                            }
                        ]
                    }
                },
                {
                    "title": "\ud83d\udcca Sheet Sync Failures (1h)",
                    "visualization": {
                        "id": "viz.billboard"
                    },
                    "layout": {
                        "column": 7,
                        "row": 1,
                        "height": 3,
                        "width": 3
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT count(*) AS 'Sheet Failures' FROM TransactionError WHERE kind IN ('sheet_upsert_fail', 'sheet_delete_fail', 'farmer_bill_sheet_fail') SINCE 1 hour ago"
                            }
                        ],
                        "thresholds": [
                            {
                                "alertSeverity": "WARNING",
                                "value": 1
                            },
                            {
                                "alertSeverity": "CRITICAL",
                                "value": 3
                            }
                        ]
                    }
                },
                {
                    "title": "\ud83d\udcb0 Settlement Errors (1h)",
                    "visualization": {
                        "id": "viz.billboard"
                    },
                    "layout": {
                        "column": 10,
                        "row": 1,
                        "height": 3,
                        "width": 3
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT count(*) AS 'Settlement Errors' FROM TransactionError WHERE kind LIKE 'settlement_%' SINCE 1 hour ago"
                            }
                        ],
                        "thresholds": [
                            {
                                "alertSeverity": "CRITICAL",
                                "value": 0
                            }
                        ]
                    }
                },
                {
                    "title": "Errors Over Time (by kind)",
                    "visualization": {
                        "id": "viz.line"
                    },
                    "layout": {
                        "column": 1,
                        "row": 4,
                        "height": 3,
                        "width": 6
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT count(*) FROM TransactionError WHERE appName = 'tender' FACET kind TIMESERIES 1 hour SINCE 1 day ago"
                            }
                        ],
                        "legend": {
                            "enabled": True
                        },
                        "yAxisLeft": {
                            "zero": True
                        }
                    }
                },
                {
                    "title": "Slowest Endpoints (avg seconds)",
                    "visualization": {
                        "id": "viz.bar"
                    },
                    "layout": {
                        "column": 7,
                        "row": 4,
                        "height": 3,
                        "width": 6
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT average(duration) AS 'Avg (s)' FROM Transaction WHERE appName = 'tender' FACET name SINCE 1 day ago LIMIT 10"
                            }
                        ]
                    }
                },
                {
                    "title": "External API Response Times",
                    "visualization": {
                        "id": "viz.line"
                    },
                    "layout": {
                        "column": 1,
                        "row": 7,
                        "height": 3,
                        "width": 6
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT average(duration) FROM External WHERE appName = 'tender' FACET `host` TIMESERIES 30 minutes SINCE 1 day ago"
                            }
                        ],
                        "legend": {
                            "enabled": True
                        },
                        "yAxisLeft": {
                            "zero": True
                        }
                    }
                },
                {
                    "title": "External API Errors (by kind)",
                    "visualization": {
                        "id": "viz.table"
                    },
                    "layout": {
                        "column": 7,
                        "row": 7,
                        "height": 3,
                        "width": 6
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT count(*) AS 'Failures' FROM TransactionError WHERE kind IN ('farmer_api_fail', 'mukkadam_sync_fail', 'bill_webhook_fail', 'outbound_webhook_fail', 'plot_crop_api_fail') FACET kind SINCE 1 day ago"
                            }
                        ]
                    }
                }
            ]
        }
    ]
}


# ====================================================================
# DASHBOARD 2: Business Decisions
# ====================================================================
DASHBOARD_2 = {
    "name": "Tender \u2014 Business Decisions",
    "description": "Weekly review: schedule rules, settlements, data quality, payments",
    "permissions": "PUBLIC_READ_WRITE",
    "pages": [
        {
            "name": "Business Decisions",
            "widgets": [
                {
                    "title": "How Are Dates Being Decided?",
                    "visualization": {
                        "id": "viz.pie"
                    },
                    "layout": {
                        "column": 1,
                        "row": 1,
                        "height": 3,
                        "width": 4
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT count(*) FROM TenderOps WHERE kind = 'schedule_rule' FACET rule SINCE 7 days ago"
                            }
                        ]
                    }
                },
                {
                    "title": "Schedule Rule Trend (30 days)",
                    "visualization": {
                        "id": "viz.stacked-bar"
                    },
                    "layout": {
                        "column": 5,
                        "row": 1,
                        "height": 3,
                        "width": 8
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT count(*) FROM TenderOps WHERE kind = 'schedule_rule' FACET rule TIMESERIES 1 day SINCE 30 days ago"
                            }
                        ],
                        "legend": {
                            "enabled": True
                        }
                    }
                },
                {
                    "title": "Plot Owner Conflicts",
                    "visualization": {
                        "id": "viz.table"
                    },
                    "layout": {
                        "column": 1,
                        "row": 4,
                        "height": 3,
                        "width": 6
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT existing_farmer, incoming_farmer, plot_code, timestamp FROM TenderOps WHERE kind = 'plot_owner_conflict_kept' SINCE 30 days ago LIMIT 50"
                            }
                        ]
                    }
                },
                {
                    "title": "Data Quality Signals",
                    "visualization": {
                        "id": "viz.billboard"
                    },
                    "layout": {
                        "column": 7,
                        "row": 4,
                        "height": 3,
                        "width": 3
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT filter(count(*), WHERE kind = 'plot_auto_created') AS 'Plots Auto-Created', filter(count(*), WHERE kind = 'crop_backfilled') AS 'Crops Backfilled', filter(count(*), WHERE kind = 'farmer_api_down_continue') AS 'Farmer API Skipped' FROM TenderOps SINCE 7 days ago"
                            }
                        ]
                    }
                },
                {
                    "title": "Mukkadam Rate Fallbacks",
                    "visualization": {
                        "id": "viz.table"
                    },
                    "layout": {
                        "column": 10,
                        "row": 4,
                        "height": 3,
                        "width": 3
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT mukkadam, farmer_rate, computed, timestamp FROM TenderOps WHERE kind = 'mukkadam_rate_fallback' SINCE 7 days ago LIMIT 50"
                            }
                        ]
                    }
                },
                {
                    "title": "Settlement Branch Distribution (30 days)",
                    "visualization": {
                        "id": "viz.stacked-bar"
                    },
                    "layout": {
                        "column": 1,
                        "row": 7,
                        "height": 3,
                        "width": 7
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT count(*) FROM TenderOps WHERE kind LIKE 'settlement_%' FACET kind TIMESERIES 1 day SINCE 30 days ago"
                            }
                        ],
                        "legend": {
                            "enabled": True
                        }
                    }
                },
                {
                    "title": "Settlement Details (7 days)",
                    "visualization": {
                        "id": "viz.table"
                    },
                    "layout": {
                        "column": 8,
                        "row": 7,
                        "height": 3,
                        "width": 5
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT kind, job_id, mukkadam, timestamp FROM TenderOps WHERE kind LIKE 'settlement_%' SINCE 7 days ago ORDER BY timestamp DESC LIMIT 100"
                            }
                        ]
                    }
                },
                {
                    "title": "Duplicate Payments Blocked",
                    "visualization": {
                        "id": "viz.billboard"
                    },
                    "layout": {
                        "column": 1,
                        "row": 10,
                        "height": 3,
                        "width": 4
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT count(*) AS 'Duplicates Blocked' FROM TenderOps WHERE kind = 'duplicate_payment_blocked' SINCE 30 days ago"
                            }
                        ]
                    }
                },
                {
                    "title": "Booking Status Changes (7 days)",
                    "visualization": {
                        "id": "viz.table"
                    },
                    "layout": {
                        "column": 5,
                        "row": 10,
                        "height": 3,
                        "width": 8
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT booking_id, new_status, total_paid, timestamp FROM TenderOps WHERE kind = 'booking_status_changed' SINCE 7 days ago ORDER BY timestamp DESC LIMIT 50"
                            }
                        ]
                    }
                }
            ]
        }
    ]
}


# ====================================================================
# DASHBOARD 3: Sheet Operations
# ====================================================================
DASHBOARD_3 = {
    "name": "Tender \u2014 Sheet Operations",
    "description": "Debugging: manual edits, cascades, sync health, unresolved names",
    "permissions": "PUBLIC_READ_WRITE",
    "pages": [
        {
            "name": "Sheet Operations",
            "widgets": [
                {
                    "title": "Manual Edits by Type",
                    "visualization": {
                        "id": "viz.bar"
                    },
                    "layout": {
                        "column": 1,
                        "row": 1,
                        "height": 3,
                        "width": 4
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT count(*) FROM TenderOps WHERE kind LIKE 'manual_%' FACET kind SINCE 7 days ago"
                            }
                        ]
                    }
                },
                {
                    "title": "Manual Edits by Person",
                    "visualization": {
                        "id": "viz.bar"
                    },
                    "layout": {
                        "column": 5,
                        "row": 1,
                        "height": 3,
                        "width": 4
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT count(*) FROM TenderOps WHERE kind LIKE 'manual_%' FACET edited_by SINCE 7 days ago"
                            }
                        ]
                    }
                },
                {
                    "title": "Edits Over Time",
                    "visualization": {
                        "id": "viz.line"
                    },
                    "layout": {
                        "column": 9,
                        "row": 1,
                        "height": 3,
                        "width": 4
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT count(*) FROM TenderOps WHERE kind LIKE 'manual_%' FACET kind TIMESERIES 1 day SINCE 30 days ago"
                            }
                        ],
                        "legend": {
                            "enabled": True
                        }
                    }
                },
                {
                    "title": "Cascade Blast Radius",
                    "visualization": {
                        "id": "viz.billboard"
                    },
                    "layout": {
                        "column": 1,
                        "row": 4,
                        "height": 3,
                        "width": 4
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT uniqueCount(trigger) AS 'Date Edits That Cascaded', count(*) AS 'Total Activities Shifted' FROM TenderOps WHERE kind = 'cascade_shift' SINCE 7 days ago"
                            }
                        ]
                    }
                },
                {
                    "title": "Cascade Details",
                    "visualization": {
                        "id": "viz.table"
                    },
                    "layout": {
                        "column": 5,
                        "row": 4,
                        "height": 3,
                        "width": 4
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT trigger, affected, shift, old, new, timestamp FROM TenderOps WHERE kind = 'cascade_shift' SINCE 7 days ago ORDER BY timestamp DESC LIMIT 50"
                            }
                        ]
                    }
                },
                {
                    "title": "Cascades Skipped (Already Allocated)",
                    "visualization": {
                        "id": "viz.table"
                    },
                    "layout": {
                        "column": 9,
                        "row": 4,
                        "height": 3,
                        "width": 4
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT ja_id, reason, timestamp FROM TenderOps WHERE kind = 'cascade_skip' SINCE 7 days ago ORDER BY timestamp DESC LIMIT 50"
                            }
                        ]
                    }
                },
                {
                    "title": "Unresolved Mukkadam Names",
                    "visualization": {
                        "id": "viz.table"
                    },
                    "layout": {
                        "column": 1,
                        "row": 7,
                        "height": 3,
                        "width": 4
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT ja_id, raw_names, edited_by, timestamp FROM TenderOps WHERE kind = 'mukkadam_unresolved' SINCE 7 days ago ORDER BY timestamp DESC"
                            }
                        ]
                    }
                },
                {
                    "title": "Sheet Sync Results (7 days)",
                    "visualization": {
                        "id": "viz.stacked-bar"
                    },
                    "layout": {
                        "column": 5,
                        "row": 7,
                        "height": 3,
                        "width": 4
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT count(*) FROM TenderOps WHERE kind IN ('sheet_row_synced', 'sheet_row_deleted', 'sheet_row_auto_removed', 'sheet_full_refresh') FACET kind TIMESERIES 1 day SINCE 7 days ago"
                            }
                        ],
                        "legend": {
                            "enabled": True
                        }
                    }
                },
                {
                    "title": "Sheet Edit Success vs Failure",
                    "visualization": {
                        "id": "viz.pie"
                    },
                    "layout": {
                        "column": 9,
                        "row": 7,
                        "height": 3,
                        "width": 4
                    },
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {
                                "accountIds": [
                                    7933695
                                ],
                                "query": "SELECT count(*) FROM TenderOps WHERE kind = 'sheet_edit_result' FACET success SINCE 7 days ago"
                            }
                        ]
                    }
                }
            ]
        }
    ]
}


def main():
    if len(sys.argv) < 2:
        print()
        print("Usage: python create_dashboards.py NRAK-YOUR-USER-API-KEY")
        print()
        print("Get your User API key from: https://one.newrelic.com/api-keys")
        print("Look for Type: USER (starts with NRAK-)")
        print()
        sys.exit(1)

    api_key = sys.argv[1]

    print()
    print("=" * 60)
    print("  Tender Dashboard — New Relic Dashboard Creator")
    print("=" * 60)
    print()

    dashboards = [
        ("1/3", DASHBOARD_1),
        ("2/3", DASHBOARD_2),
        ("3/3", DASHBOARD_3),
    ]

    created = 0
    for label, config in dashboards:
        print(f"[{label}] Creating: {config['name']}...")
        guid = create_dashboard(api_key, config)
        if guid:
            created += 1
        print()

    print("-" * 60)
    if created == 3:
        print(f"✅ All {created} dashboards created successfully!")
        print()
        print("Open them at: https://one.newrelic.com/dashboards")
    else:
        print(f"⚠️  {created}/3 dashboards created. Check errors above.")
    print()


if __name__ == "__main__":
    main()
