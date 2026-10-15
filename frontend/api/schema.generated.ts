export interface paths {
    "/api/admin/billing/purchases/{purchase_id}/refund": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Refund Purchase
         * @description Ask Paddle to refund an **unused** pack in full. The lot is frozen and a durable intent written
         *     first; a pack with spent or running units goes to manual review instead. The units are taken back only
         *     when Paddle reports the refund approved. Repeating the call never creates a second refund.
         */
        post: operations["refund_purchase_api_admin_billing_purchases__purchase_id__refund_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/credits/adjust": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Adjust Credits
         * @description Add or remove credits. Repeating the same `idempotency_key` changes nothing and reports `applied:
         *     false`.
         */
        post: operations["adjust_credits_api_admin_credits_adjust_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/flags": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Flags */
        get: operations["list_flags_api_admin_flags_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/flags/{key}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Update Flag */
        put: operations["update_flag_api_admin_flags__key__put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/flags/{key}/overrides/{user_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Put Override */
        put: operations["put_override_api_admin_flags__key__overrides__user_id__put"];
        post?: never;
        /** Delete Override */
        delete: operations["delete_override_api_admin_flags__key__overrides__user_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/jobs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Inspect Jobs
         * @description Procrastinate job metadata: counts per queue and status, and the newest jobs. Never the arguments.
         */
        get: operations["inspect_jobs_api_admin_jobs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/users/{user_id}/billing-hold/clear": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Clear Hold
         * @description End a billing review (units were consumed before a purchase was reversed). The note and the admin are
         *     logged; reports already made stay readable, and nothing is claimed back.
         */
        post: operations["clear_hold_api_admin_users__user_id__billing_hold_clear_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/audits": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Audits
         * @description The caller's audits, newest first, by keyset over `(created_at, id)`: a row inserted between two
         *     requests never repeats or skips a row. Another user's cursor only ever pages the caller's own rows.
         */
        get: operations["list_audits_api_audits_get"];
        put?: never;
        /** Create Audit */
        post: operations["create_audit_api_audits_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/audits/{audit_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Audit */
        get: operations["get_audit_api_audits__audit_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/audits/{audit_id}/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Audit Events
         * @description Server-sent progress. Replays every event after `Last-Event-ID`, then streams live; the first terminal
         *     event (`done` or `error`) ends the stream. Another tenant's or an unknown audit is a 404.
         */
        get: operations["audit_events_api_audits__audit_id__events_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/email/start": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Email Start
         * @description Always 204: the response never reveals whether the address has an account.
         */
        post: operations["email_start_api_auth_email_start_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/email/verify": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Email Verify */
        post: operations["email_verify_api_auth_email_verify_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/google": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Google Sign In */
        post: operations["google_sign_in_api_auth_google_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Login
         * @description One generic failure for every cause (wrong password, unknown address, an account with no password), and
         *     a real hash check even for an unknown address, so neither the body nor the response time says which. A
         *     throttle is not a lockout: past the limit the answer is 429, and the right password works again once the
         *     window has passed.
         */
        post: operations["login_api_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/password/change": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Password Change
         * @description Needs the current password. Signs out every session including this one: the person logs in again.
         */
        post: operations["password_change_api_auth_password_change_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/password/forgot": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Password Forgot
         * @description Always 202. A reset link is mailed only when the address has an account, and nothing in the answer says
         *     whether it does. The link goes to the configured app origin, never to a host taken from the request.
         */
        post: operations["password_forgot_api_auth_password_forgot_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/password/reset": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Password Reset
         * @description Set the password (the first one, for an account made by Google or a magic link) and sign everyone out.
         *     Nobody is signed in by this: the person logs in again with the new password.
         */
        post: operations["password_reset_api_auth_password_reset_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/register": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Register */
        post: operations["register_api_auth_register_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/register/resend": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Register Resend
         * @description Re-mail a pending registration with a fresh token (the old link stops working). The password hash
         *     stays the one chosen at registration; an address with no pending registration gets nothing.
         */
        post: operations["register_resend_api_auth_register_resend_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/register/verify": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Register Verify */
        post: operations["register_verify_api_auth_register_verify_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Sessions */
        get: operations["list_sessions_api_auth_sessions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/signout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Sign Out
         * @description Idempotent: signing out without a valid session still clears the cookie.
         */
        post: operations["sign_out_api_auth_signout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/signout-all": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Sign Out Everywhere */
        post: operations["sign_out_everywhere_api_auth_signout_all_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/billing/checkout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Checkout */
        post: operations["checkout_api_billing_checkout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/billing/packs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Packs */
        get: operations["list_packs_api_billing_packs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/billing/purchases": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Purchases */
        get: operations["list_purchases_api_billing_purchases_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/billing/purchases/{purchase_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Purchase */
        get: operations["get_purchase_api_billing_purchases__purchase_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/billing/purchases/{purchase_id}/invoice": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Invoice
         * @description The seller's document for this sale, obtained from Paddle on demand after the ownership check.
         *     Paddle is the seller and issues it; the product issues no second customer invoice for the same sale.
         */
        get: operations["get_invoice_api_billing_purchases__purchase_id__invoice_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * My Profile
         * @description Profile, plan, credits, feature flags and the Otodom circuit-breaker state, in one call for the SPA.
         */
        get: operations["my_profile_api_me_get"];
        put?: never;
        post?: never;
        /**
         * Delete My Account
         * @description Erase the account. Idempotent and retryable: the processor is erased first, so a failure at either
         *     step leaves
         *     the request safe to repeat (deleting an already deleted Stripe customer succeeds).
         */
        delete: operations["delete_my_account_api_me_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/me/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Export My Data
         * @description Everything we hold about the caller as one JSON document (access request). Limited to 5 per hour.
         */
        get: operations["export_my_data_api_me_export_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/saved": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Saved */
        get: operations["list_saved_api_saved_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/saved/{otodom_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Save Listing */
        put: operations["save_listing_api_saved__otodom_id__put"];
        post?: never;
        /**
         * Unsave Listing
         * @description Idempotent: unsaving something that is not saved is still 204.
         */
        delete: operations["unsave_listing_api_saved__otodom_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * Accepted
         * @description The body of every non-enumerating 202: identical whatever the address is.
         */
        Accepted: Record<string, never>;
        /**
         * AccountDelete
         * @description Account erasure must be confirmed by typing the account's own address (GDPR[erasure]).
         */
        AccountDelete: {
            /** Confirm Email */
            confirm_email: string;
        };
        /** AuditAccepted */
        AuditAccepted: {
            /**
             * Audit Id
             * Format: uuid
             */
            audit_id: string;
            /**
             * Credits Remaining
             * @description None: the audit is within the plan allowance
             */
            credits_remaining: number | null;
            /** Events Url */
            events_url: string;
            status: components["schemas"]["AuditState"];
        };
        /**
         * AuditCreate
         * @description `listing_ref` is bounded here and normalised to the short Otodom id by the route
         *     (`rm_core.listing_ref.parse_listing_ref`, which rejects anything but an Otodom URL or id).
         */
        AuditCreate: {
            /**
             * Analyst
             * @default false
             */
            analyst: boolean;
            /**
             * Lang
             * @default pl
             * @enum {string}
             */
            lang: "pl" | "en";
            /** Listing Ref */
            listing_ref: string;
        };
        /**
         * AuditOut
         * @description One audit. Money columns are copied from `result` by the worker, never computed by the API.
         */
        AuditOut: {
            /** Asking Price Pln */
            asking_price_pln: string | null;
            /**
             * Audit Id
             * Format: uuid
             */
            audit_id: string;
            /** Capex Pln */
            capex_pln: string | null;
            charge_state: components["schemas"]["ChargeStateName"];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Error Code */
            error_code: string | null;
            /** Finished At */
            finished_at: string | null;
            /** Grade */
            grade: string | null;
            /** Irr 10Y */
            irr_10y: string | null;
            /** Max Bid Pln */
            max_bid_pln: string | null;
            /** Otodom Id */
            otodom_id: string;
            /**
             * Result
             * @description canonical DealAnalysis JSON; null until a terminal success. Its shape is docs/deal-analysis.schema.json for the version in `result.schema_version`
             */
            result: {
                [key: string]: unknown;
            } | null;
            /** Started At */
            started_at: string | null;
            status: components["schemas"]["AuditState"];
        };
        /**
         * AuditPage
         * @description One page of the caller's audits, newest first. There is deliberately no total: an exact count under
         *     filters is a scan per request, and a cursor is all a list needs.
         */
        AuditPage: {
            /** Items */
            items: components["schemas"]["AuditSummary"][];
            /**
             * Next Cursor
             * @description opaque; pass it back as `cursor` for the next page. null: this was the last page
             */
            next_cursor: string | null;
        };
        /**
         * AuditState
         * @description Mirrors `rm_core.db.models.AuditStatus`; `tests/unit/test_audit_contracts.py` fails if they drift.
         * @enum {string}
         */
        AuditState: "queued" | "running" | "succeeded" | "succeeded_degraded" | "rejected" | "failed_input" | "failed_upstream" | "failed_internal" | "cancelled";
        /**
         * AuditSummary
         * @description List row: the same fields without the full result.
         */
        AuditSummary: {
            /** Asking Price Pln */
            asking_price_pln: string | null;
            /**
             * Audit Id
             * Format: uuid
             */
            audit_id: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Error Code */
            error_code: string | null;
            /** Finished At */
            finished_at: string | null;
            /** Grade */
            grade: string | null;
            /** Max Bid Pln */
            max_bid_pln: string | null;
            /** Otodom Id */
            otodom_id: string;
            status: components["schemas"]["AuditState"];
        };
        /**
         * BillingHoldClear
         * @description Staff resolved a billing review; the note is the record of why (logged with the admin's id).
         */
        BillingHoldClear: {
            /** Note */
            note: string;
        };
        /** BillingHoldOut */
        BillingHoldOut: {
            /** Cleared */
            cleared: boolean;
        };
        /** ChangePasswordRequest */
        ChangePasswordRequest: {
            /** Current Password */
            current_password: string;
            /** New Password */
            new_password: string;
        };
        /**
         * ChargeStateName
         * @description Mirrors `rm_core.db.models.ChargeState`.
         * @enum {string}
         */
        ChargeStateName: "reserved" | "captured" | "released";
        /** CheckoutRequest */
        CheckoutRequest: {
            /**
             * Pack Code
             * @enum {string}
             */
            pack_code: "reports_1" | "reports_5" | "reports_10";
        };
        /**
         * CreditAdjust
         * @description `idempotency_key` is chosen by the caller; repeating it never adjusts twice.
         */
        CreditAdjust: {
            /** Delta */
            delta: number;
            /**
             * Idempotency Key
             * Format: uuid
             */
            idempotency_key: string;
            /** Note */
            note: string;
            /** User Id */
            user_id: string;
        };
        /** CreditAdjustOut */
        CreditAdjustOut: {
            /** Applied */
            applied: boolean;
            /** Balance */
            balance: number;
        };
        /** EmailStart */
        EmailStart: {
            /** Email */
            email: string;
        };
        /** EmailVerify */
        EmailVerify: {
            /** Token */
            token: string;
        };
        /** ExportAudit */
        ExportAudit: {
            /** Asking Price Pln */
            asking_price_pln: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Error Code */
            error_code: string | null;
            /** Finished At */
            finished_at: string | null;
            /** Grade */
            grade: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Lang */
            lang: string;
            /** Max Bid Pln */
            max_bid_pln: string | null;
            /** Otodom Id */
            otodom_id: string;
            /** Result */
            result: {
                [key: string]: unknown;
            } | null;
            /** Status */
            status: string;
        };
        /** ExportIdentity */
        ExportIdentity: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Provider */
            provider: string;
            /** Subject */
            subject: string;
        };
        /** ExportLedgerEntry */
        ExportLedgerEntry: {
            /** Audit Id */
            audit_id: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Delta */
            delta: number;
            /** Note */
            note: string | null;
            /** Reason */
            reason: string;
        };
        /** ExportOverride */
        ExportOverride: {
            /** Enabled */
            enabled: boolean;
            /** Expires At */
            expires_at: string | null;
            /** Flag Key */
            flag_key: string;
            /** Reason */
            reason: string;
        };
        /** ExportProfile */
        ExportProfile: {
            /** Avatar Url */
            avatar_url: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Email */
            email: string;
            /** Email Verified At */
            email_verified_at: string | null;
            /** Id */
            id: string;
            /** Name */
            name: string | null;
            /** Role */
            role: string;
        };
        /** ExportSaved */
        ExportSaved: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Note */
            note: string | null;
            /** Otodom Id */
            otodom_id: string;
        };
        /** ExportSession */
        ExportSession: {
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /** Ip */
            ip: string | null;
            /**
             * Last Seen At
             * Format: date-time
             */
            last_seen_at: string;
            /** User Agent */
            user_agent: string | null;
        };
        /** ExportSubscription */
        ExportSubscription: {
            /** Cancel At Period End */
            cancel_at_period_end: boolean;
            /**
             * Current Period End
             * Format: date-time
             */
            current_period_end: string;
            /**
             * Current Period Start
             * Format: date-time
             */
            current_period_start: string;
            /** Id */
            id: string;
            /** Plan Code */
            plan_code: string;
            /** Status */
            status: string;
        };
        /** ExportUsagePeriod */
        ExportUsagePeriod: {
            /** Allowance */
            allowance: number;
            /** Kind */
            kind: string;
            /**
             * Period End
             * Format: date-time
             */
            period_end: string;
            /**
             * Period Start
             * Format: date-time
             */
            period_start: string;
            /** Used */
            used: number;
        };
        /** FlagOut */
        FlagOut: {
            /** Description */
            description: string;
            /** Enabled Default */
            enabled_default: boolean;
            /** Key */
            key: string;
            /** Min Plan */
            min_plan: string | null;
            /** Overrides */
            overrides: number;
            /** Rollout Pct */
            rollout_pct: number;
        };
        /**
         * FlagUpdate
         * @description Only the fields present are changed; flags themselves are created by the seed, not through the API.
         */
        FlagUpdate: {
            /**
             * Clear Min Plan
             * @default false
             */
            clear_min_plan: boolean;
            /** Enabled Default */
            enabled_default?: boolean | null;
            /** Min Plan */
            min_plan?: ("free" | "pro") | null;
            /** Rollout Pct */
            rollout_pct?: number | null;
        };
        /** ForgotRequest */
        ForgotRequest: {
            /** Email */
            email: string;
        };
        /** GoogleCredential */
        GoogleCredential: {
            /** Credential */
            credential: string;
        };
        /**
         * InvoiceOut
         * @description A link to the document Paddle issued for this sale. Short-lived: fetched on demand, never stored.
         */
        InvoiceOut: {
            /** Url */
            url: string;
        };
        /**
         * JobOut
         * @description Metadata only: job arguments are never returned (they can hold addresses and login tokens, L-011).
         */
        JobOut: {
            /** Attempts */
            attempts: number;
            /** Id */
            id: number;
            /** Queue */
            queue: string;
            /** Scheduled At */
            scheduled_at: string | null;
            /** Status */
            status: string;
            /** Task */
            task: string;
        };
        /** JobsOut */
        JobsOut: {
            /** Counts */
            counts: {
                [key: string]: {
                    [key: string]: number;
                };
            };
            /** Recent */
            recent: components["schemas"]["JobOut"][];
        };
        /** LoginRequest */
        LoginRequest: {
            /** Email */
            email: string;
            /** Password */
            password: string;
        };
        /** MeDetailOut */
        MeDetailOut: {
            /** Avatar Url */
            avatar_url: string | null;
            /** Credit Balance */
            credit_balance: number;
            /** Email */
            email: string;
            /** Email Verified */
            email_verified: boolean;
            /** Flags */
            flags: {
                [key: string]: boolean;
            };
            /** Id */
            id: string;
            /** Name */
            name: string | null;
            plan: components["schemas"]["PlanOut"];
            /** Role */
            role: string;
            upstream: components["schemas"]["UpstreamOut"];
        };
        /**
         * MeOut
         * @description GDPR[personal-data]: email, name, avatar_url returned to the owner of the account only.
         */
        MeOut: {
            /** Avatar Url */
            avatar_url: string | null;
            /** Email */
            email: string;
            /** Email Verified */
            email_verified: boolean;
            /** Id */
            id: string;
            /** Name */
            name: string | null;
            /** Role */
            role: string;
        };
        /** OverrideOut */
        OverrideOut: {
            /** Created By */
            created_by: string;
            /** Enabled */
            enabled: boolean;
            /** Expires At */
            expires_at: string | null;
            /** Flag Key */
            flag_key: string;
            /** Reason */
            reason: string;
            /** User Id */
            user_id: string;
        };
        /** OverridePut */
        OverridePut: {
            /** Enabled */
            enabled: boolean;
            /** Expires At */
            expires_at?: string | null;
            /** Reason */
            reason: string;
        };
        /** PackOut */
        PackOut: {
            /** Catalog Version */
            catalog_version: number;
            /**
             * Code
             * @enum {string}
             */
            code: "reports_1" | "reports_5" | "reports_10";
            /**
             * Currency
             * @default PLN
             * @constant
             */
            currency: "PLN";
            /** Gross Pln */
            gross_pln: string;
            /** Reports */
            reports: number;
        };
        /** PacksOut */
        PacksOut: {
            /** Enabled */
            enabled: boolean;
            /** Packs */
            packs: components["schemas"]["PackOut"][];
        };
        /** PeriodOut */
        PeriodOut: {
            /** Allowance */
            allowance: number;
            /** Kind */
            kind: string;
            /**
             * Period End
             * Format: date-time
             */
            period_end: string;
            /** Remaining */
            remaining: number;
            /** Used */
            used: number;
        };
        /** PlanOut */
        PlanOut: {
            /**
             * Code
             * @enum {string}
             */
            code: "free" | "pro";
            /** Grace Until */
            grace_until: string | null;
            /** Is Pro */
            is_pro: boolean;
            period: components["schemas"]["PeriodOut"] | null;
            /** Subscription Status */
            subscription_status: string | null;
        };
        /**
         * Problem
         * @description The body of every error response (RFC 9457, `application/problem+json`). `code` is the stable part a
         *     client branches on; `title` and `detail` are for people. Some codes add fields of their own (for example
         *     `audit_id` on `AUDIT_IN_PROGRESS`, `upgrade_url` on `QUOTA_EXHAUSTED`), so extra keys are allowed.
         */
        Problem: {
            code: components["schemas"]["ProblemCode"];
            /**
             * Detail
             * @default null
             */
            detail: string | null;
            /**
             * Errors
             * @description validation errors, 422 only
             * @default null
             */
            errors: components["schemas"]["ProblemField"][] | null;
            /**
             * Instance
             * @description the request path
             */
            instance: string;
            /**
             * Request Id
             * @default null
             */
            request_id: string | null;
            /** Status */
            status: number;
            /** Title */
            title: string;
            /**
             * Type
             * @description `urn:rentmonitor:problem:<code>`
             */
            type: string;
        } & {
            [key: string]: unknown;
        };
        /**
         * ProblemCode
         * @enum {string}
         */
        ProblemCode: "INVALID_LISTING_REF" | "QUOTA_EXHAUSTED" | "AUDIT_IN_PROGRESS" | "RENT_NOT_DEAL" | "FRACTIONAL_OWNERSHIP" | "LISTING_GONE" | "UPSTREAM_BLOCKED" | "UPSTREAM_SCHEMA_DRIFT" | "VISION_UNAVAILABLE" | "CONTEXT_UNAVAILABLE" | "INTERNAL" | "VALIDATION_ERROR" | "NOT_FOUND" | "HTTP_ERROR" | "NOT_READY" | "INVALID_GOOGLE_TOKEN" | "GOOGLE_EMAIL_UNVERIFIED" | "EMAIL_CONFIRMATION_REQUIRED" | "MAGIC_LINK_INVALID" | "INVALID_CREDENTIALS" | "WEAK_PASSWORD" | "AUTH_TOKEN_INVALID" | "ACCOUNT_EXISTS" | "BILLING_UNAVAILABLE" | "IDEMPOTENCY_CONFLICT" | "BILLING_PROVIDER_ERROR" | "INVALID_WEBHOOK_SIGNATURE" | "BILLING_HOLD" | "PURCHASE_NOT_REFUNDABLE" | "REFUND_NEEDS_REVIEW" | "EMAIL_NOT_VERIFIED" | "FEATURE_NOT_IN_PLAN" | "ADMIN_ONLY" | "ALREADY_SUBSCRIBED" | "INVALID_STRIPE_SIGNATURE" | "UNAUTHENTICATED" | "RATE_LIMITED" | "ORIGIN_NOT_ALLOWED" | "CONFIRMATION_MISMATCH" | "CREDIT_BELOW_ZERO" | "SAVED_LIMIT_REACHED";
        /**
         * ProblemField
         * @description One rejected input in a 422: where (`loc`), the rule (`type`) and a message. Never the value itself.
         */
        ProblemField: {
            /** Loc */
            loc: string[];
            /** Msg */
            msg: string;
            /** Type */
            type: string;
        };
        /**
         * PurchaseOut
         * @description GDPR[personal-data]: returned to the buyer only. No raw provider payload, no binding token.
         */
        PurchaseOut: {
            /** Checkout Url */
            checkout_url: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Currency
             * @default PLN
             * @constant
             */
            currency: "PLN";
            /** Granted At */
            granted_at: string | null;
            /** Gross Pln */
            gross_pln: string;
            /**
             * Pack Code
             * @enum {string}
             */
            pack_code: "reports_1" | "reports_5" | "reports_10";
            /**
             * Purchase Id
             * Format: uuid
             */
            purchase_id: string;
            /** Refunded At */
            refunded_at: string | null;
            /** Reports */
            reports: number;
            /**
             * State
             * @enum {string}
             */
            state: "intent" | "creating" | "created" | "creation_unknown" | "failed" | "paid" | "granted" | "review" | "refunded";
            /** Transaction Id */
            transaction_id: string | null;
        };
        /** PurchasesOut */
        PurchasesOut: {
            /** Purchases */
            purchases: components["schemas"]["PurchaseOut"][];
        };
        /** RefundOut */
        RefundOut: {
            /** Adjustment Id */
            adjustment_id: string | null;
            /**
             * Status
             * @enum {string}
             */
            status: "requested" | "exists" | "unknown";
        };
        /**
         * RefundRequest
         * @description Support's reason, sent to Paddle with the request (never shown to the buyer by us).
         */
        RefundRequest: {
            /** Reason */
            reason: string;
        };
        /**
         * RegisterRequest
         * @description GDPR[personal-data]: the address and a password that is hashed before it is stored.
         */
        RegisterRequest: {
            /** Email */
            email: string;
            /** Password */
            password: string;
        };
        /** RegisterVerify */
        RegisterVerify: {
            /** Token */
            token: string;
        };
        /** ResendRequest */
        ResendRequest: {
            /** Email */
            email: string;
        };
        /** ResetRequest */
        ResetRequest: {
            /** Password */
            password: string;
            /** Token */
            token: string;
        };
        /**
         * SavedOut
         * @description GDPR[personal-data]: `note` is free text written by the user.
         */
        SavedOut: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Latest Audit Id */
            latest_audit_id: string | null;
            /** Note */
            note: string | null;
            /** Otodom Id */
            otodom_id: string;
        };
        /** SavedPut */
        SavedPut: {
            /** Note */
            note?: string | null;
        };
        /**
         * SessionOut
         * @description One signed-in browser. GDPR[personal-data]: user_agent and ip belong to the account owner.
         */
        SessionOut: {
            /**
             * Created Hint
             * Format: date-time
             * @description last_seen_at; sessions carry no separate creation time
             */
            created_hint: string;
            /** Current */
            current: boolean;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /** Id */
            id: number;
            /** Ip */
            ip: string | null;
            /** User Agent */
            user_agent: string | null;
        };
        /**
         * UpstreamOut
         * @description Shown as "Otodom is rate-limiting us, try in N minutes" instead of a spinner (blueprint §2).
         */
        UpstreamOut: {
            /** Otodom Breaker Open */
            otodom_breaker_open: boolean;
            /** Reason */
            reason: string | null;
            /** Retry After S */
            retry_after_s: number;
        };
        /** UserDataExport */
        UserDataExport: {
            /** Audits */
            audits: components["schemas"]["ExportAudit"][];
            /** Credit Balance */
            credit_balance: number | null;
            /** Credit Ledger */
            credit_ledger: components["schemas"]["ExportLedgerEntry"][];
            /**
             * Exported At
             * Format: date-time
             */
            exported_at: string;
            /** Feature Overrides */
            feature_overrides: components["schemas"]["ExportOverride"][];
            /** Identities */
            identities: components["schemas"]["ExportIdentity"][];
            profile: components["schemas"]["ExportProfile"];
            /** Saved Listings */
            saved_listings: components["schemas"]["ExportSaved"][];
            /** Sessions */
            sessions: components["schemas"]["ExportSession"][];
            /** Subscriptions */
            subscriptions: components["schemas"]["ExportSubscription"][];
            /** Usage Periods */
            usage_periods: components["schemas"]["ExportUsagePeriod"][];
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    refund_purchase_api_admin_billing_purchases__purchase_id__refund_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                purchase_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RefundRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RefundOut"];
                };
            };
            /** @description Accepted */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RefundOut"];
                };
            };
            /** @description Problem: UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: ADMIN_ONLY, ORIGIN_NOT_ALLOWED */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: PURCHASE_NOT_REFUNDABLE, REFUND_NEEDS_REVIEW */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: BILLING_PROVIDER_ERROR */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: BILLING_UNAVAILABLE, NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    adjust_credits_api_admin_credits_adjust_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreditAdjust"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CreditAdjustOut"];
                };
            };
            /** @description Problem: UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: ADMIN_ONLY, ORIGIN_NOT_ALLOWED */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_FOUND */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: CREDIT_BELOW_ZERO */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    list_flags_api_admin_flags_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FlagOut"][];
                };
            };
            /** @description Problem: UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: ADMIN_ONLY */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    update_flag_api_admin_flags__key__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                key: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FlagUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FlagOut"];
                };
            };
            /** @description Problem: UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: ADMIN_ONLY, ORIGIN_NOT_ALLOWED */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_FOUND */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    put_override_api_admin_flags__key__overrides__user_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                key: string;
                user_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OverridePut"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OverrideOut"];
                };
            };
            /** @description Problem: UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: ADMIN_ONLY, ORIGIN_NOT_ALLOWED */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_FOUND */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    delete_override_api_admin_flags__key__overrides__user_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                key: string;
                user_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Problem: UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: ADMIN_ONLY, ORIGIN_NOT_ALLOWED */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    inspect_jobs_api_admin_jobs_get: {
        parameters: {
            query?: {
                queue?: string | null;
                status?: ("todo" | "doing" | "succeeded" | "failed" | "cancelled" | "aborting" | "aborted") | null;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JobsOut"];
                };
            };
            /** @description Problem: UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: ADMIN_ONLY */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    clear_hold_api_admin_users__user_id__billing_hold_clear_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BillingHoldClear"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BillingHoldOut"];
                };
            };
            /** @description Problem: UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: ADMIN_ONLY, ORIGIN_NOT_ALLOWED */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_FOUND */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    list_audits_api_audits_get: {
        parameters: {
            query?: {
                limit?: number;
                /** @description `next_cursor` of the previous page */
                cursor?: string | null;
                /** @description repeat to match any of several */
                status?: components["schemas"]["AuditState"][] | null;
                grade?: string | null;
                /** @description Otodom id prefix */
                q?: string | null;
                /** @description the `Idempotency-Key` of a POST: did that exact request create an audit? */
                request_key?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuditPage"];
                };
            };
            /** @description Problem: UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    create_audit_api_audits_post: {
        parameters: {
            query?: never;
            header?: {
                /** @description A UUID per submission. Repeating it returns the audit it created and never reserves again; used for a different listing it is 409 IDEMPOTENCY_CONFLICT. */
                "Idempotency-Key"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AuditCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuditAccepted"];
                };
            };
            /** @description Problem: UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: QUOTA_EXHAUSTED */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: BILLING_HOLD, FEATURE_NOT_IN_PLAN, ORIGIN_NOT_ALLOWED */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: AUDIT_IN_PROGRESS, IDEMPOTENCY_CONFLICT */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INVALID_LISTING_REF, VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    get_audit_api_audits__audit_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                audit_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuditOut"];
                };
            };
            /** @description Problem: UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_FOUND */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    audit_events_api_audits__audit_id__events_get: {
        parameters: {
            query?: never;
            header?: {
                "Last-Event-ID"?: string | null;
            };
            path: {
                audit_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description progress, then done or error */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/event-stream": unknown;
                };
            };
            /** @description Problem: UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_FOUND */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    email_start_api_auth_email_start_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EmailStart"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Problem: ORIGIN_NOT_ALLOWED */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: RATE_LIMITED */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    email_verify_api_auth_email_verify_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EmailVerify"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MeOut"];
                };
            };
            /** @description Problem: MAGIC_LINK_INVALID */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: ORIGIN_NOT_ALLOWED */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    google_sign_in_api_auth_google_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GoogleCredential"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MeOut"];
                };
            };
            /** @description Problem: EMAIL_CONFIRMATION_REQUIRED, GOOGLE_EMAIL_UNVERIFIED, INVALID_GOOGLE_TOKEN */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: ORIGIN_NOT_ALLOWED */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    login_api_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MeOut"];
                };
            };
            /** @description Problem: INVALID_CREDENTIALS */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: ORIGIN_NOT_ALLOWED */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: RATE_LIMITED */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    password_change_api_auth_password_change_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ChangePasswordRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Problem: INVALID_CREDENTIALS, UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: ORIGIN_NOT_ALLOWED */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR, WEAK_PASSWORD */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: RATE_LIMITED */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    password_forgot_api_auth_password_forgot_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ForgotRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Accepted"];
                };
            };
            /** @description Problem: ORIGIN_NOT_ALLOWED */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: RATE_LIMITED */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    password_reset_api_auth_password_reset_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResetRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Problem: AUTH_TOKEN_INVALID */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: ORIGIN_NOT_ALLOWED */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR, WEAK_PASSWORD */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: RATE_LIMITED */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    register_api_auth_register_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RegisterRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Accepted"];
                };
            };
            /** @description Problem: ORIGIN_NOT_ALLOWED */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR, WEAK_PASSWORD */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: RATE_LIMITED */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    register_resend_api_auth_register_resend_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResendRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Accepted"];
                };
            };
            /** @description Problem: ORIGIN_NOT_ALLOWED */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: RATE_LIMITED */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    register_verify_api_auth_register_verify_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RegisterVerify"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MeOut"];
                };
            };
            /** @description Problem: AUTH_TOKEN_INVALID */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: ORIGIN_NOT_ALLOWED */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: ACCOUNT_EXISTS */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: RATE_LIMITED */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    list_sessions_api_auth_sessions_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionOut"][];
                };
            };
            /** @description Problem: UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    sign_out_api_auth_signout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Problem: ORIGIN_NOT_ALLOWED */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    sign_out_everywhere_api_auth_signout_all_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Problem: UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: ORIGIN_NOT_ALLOWED */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    checkout_api_billing_checkout_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CheckoutRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PurchaseOut"];
                };
            };
            /** @description Accepted */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PurchaseOut"];
                };
            };
            /** @description Problem: UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: BILLING_HOLD, EMAIL_NOT_VERIFIED, ORIGIN_NOT_ALLOWED */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: IDEMPOTENCY_CONFLICT */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: RATE_LIMITED */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: BILLING_PROVIDER_ERROR */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: BILLING_UNAVAILABLE, NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    list_packs_api_billing_packs_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PacksOut"];
                };
            };
            /** @description Problem: UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    list_purchases_api_billing_purchases_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PurchasesOut"];
                };
            };
            /** @description Problem: UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    get_purchase_api_billing_purchases__purchase_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                purchase_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PurchaseOut"];
                };
            };
            /** @description Problem: UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_FOUND */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    get_invoice_api_billing_purchases__purchase_id__invoice_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                purchase_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InvoiceOut"];
                };
            };
            /** @description Problem: UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_FOUND */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: PURCHASE_NOT_REFUNDABLE */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: RATE_LIMITED */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: BILLING_PROVIDER_ERROR */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: BILLING_UNAVAILABLE, NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    my_profile_api_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MeDetailOut"];
                };
            };
            /** @description Problem: UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    delete_my_account_api_me_delete: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AccountDelete"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Problem: UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: ORIGIN_NOT_ALLOWED */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: CONFIRMATION_MISMATCH, VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    export_my_data_api_me_export_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserDataExport"];
                };
            };
            /** @description Problem: UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: RATE_LIMITED */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    list_saved_api_saved_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SavedOut"][];
                };
            };
            /** @description Problem: UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    save_listing_api_saved__otodom_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                otodom_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SavedPut"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SavedOut"];
                };
            };
            /** @description Problem: UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: ORIGIN_NOT_ALLOWED */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_FOUND */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: SAVED_LIMIT_REACHED */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
    unsave_listing_api_saved__otodom_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                otodom_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Problem: UNAUTHENTICATED */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: ORIGIN_NOT_ALLOWED */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: VALIDATION_ERROR */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERNAL */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: NOT_READY */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
        };
    };
}
