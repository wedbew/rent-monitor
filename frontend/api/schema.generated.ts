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
    "/api/audits/{audit_id}/media": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Media Manifest */
        get: operations["read_media_manifest_api_audits__audit_id__media_get"];
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
    "/api/interior/catalogue": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Catalogue Status
         * @description Whether a product source is connected, and whether it is only a demo. Cheap: no provider call.
         */
        get: operations["catalogue_status_api_interior_catalogue_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/interior/catalogue/demo-image/{product_id}/{variant_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Demo Product Image
         * @description A generated placeholder picture for the demo source only: not a product photo and labelled as such.
         */
        get: operations["demo_product_image_api_interior_catalogue_demo_image__product_id___variant_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/interior/projects": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Projects */
        get: operations["list_projects_api_interior_projects_get"];
        put?: never;
        /** Create Project */
        post: operations["create_project_api_interior_projects_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/interior/projects/{project_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Project */
        get: operations["get_project_api_interior_projects__project_id__get"];
        /**
         * Update Project
         * @description Rename and re-brief. The 30-day lifetime is not extended by editing.
         */
        put: operations["update_project_api_interior_projects__project_id__put"];
        post?: never;
        /** Delete Project */
        delete: operations["delete_project_api_interior_projects__project_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/interior/projects/{project_id}/catalogue/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Search Catalogue
         * @description Real offers from the connected source, hard-filtered (stock, freshness, budget, text) and ordered
         *     deterministically. Nothing is estimated; an unknown price or delivery is flagged, not guessed.
         */
        get: operations["search_catalogue_api_interior_projects__project_id__catalogue_search_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/interior/projects/{project_id}/generations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Generations */
        get: operations["list_generations_api_interior_projects__project_id__generations_get"];
        put?: never;
        /**
         * Create Generation
         * @description Turn a saved revision into an illustrative picture. 202 when queued; 200 when the same revision is
         *     already queued or running (or the key was seen): a repeated click never submits or pays twice.
         */
        post: operations["create_generation_api_interior_projects__project_id__generations_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/interior/projects/{project_id}/generations/{generation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Generation */
        get: operations["get_generation_api_interior_projects__project_id__generations__generation_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/interior/projects/{project_id}/generations/{generation_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Cancel Generation
         * @description Queued-only: a running operation may already be at the provider and answers 409 `running`.
         */
        post: operations["cancel_generation_api_interior_projects__project_id__generations__generation_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/interior/projects/{project_id}/items": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Add Item
         * @description Only `name` is required; photo, price and link are optional. An absent price stays unknown.
         */
        post: operations["add_item_api_interior_projects__project_id__items_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/interior/projects/{project_id}/items/{item_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Update Item */
        put: operations["update_item_api_interior_projects__project_id__items__item_id__put"];
        post?: never;
        /** Delete Item */
        delete: operations["delete_item_api_interior_projects__project_id__items__item_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/interior/projects/{project_id}/items/{item_id}/photo": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Upload Item Photo
         * @description A photo of the person's own item; replaces the previous one (its bytes are queued for deletion).
         */
        put: operations["upload_item_photo_api_interior_projects__project_id__items__item_id__photo_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/interior/projects/{project_id}/media/{media_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Photo
         * @description An image the caller owns, served only here (no bucket URL exists). Never cached by shared caches.
         */
        get: operations["read_photo_api_interior_projects__project_id__media__media_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/interior/projects/{project_id}/revisions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Create Revision
         * @description Snapshot the brief, items and current room photo. Immutable; later edits do not change it.
         */
        post: operations["create_revision_api_interior_projects__project_id__revisions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/interior/projects/{project_id}/selections": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Select Product
         * @description Pick an exact variant. The server fetches the offer from the source itself and stores that observation;
         *     the client's idea of the price is never accepted.
         */
        post: operations["select_product_api_interior_projects__project_id__selections_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/interior/projects/{project_id}/selections/{selection_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Set Selection Quantity */
        put: operations["set_selection_quantity_api_interior_projects__project_id__selections__selection_id__put"];
        post?: never;
        /** Delete Selection */
        delete: operations["delete_selection_api_interior_projects__project_id__selections__selection_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/interior/projects/{project_id}/selections/{selection_id}/refresh": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Refresh Selection
         * @description Check the exact variant again at the source and keep the new observation (or mark it unavailable).
         */
        post: operations["refresh_selection_api_interior_projects__project_id__selections__selection_id__refresh_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/interior/projects/{project_id}/source": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Upload Source Photo
         * @description The room photo, as raw JPEG/PNG/WebP bytes (at most 10 MB). Normalised, stripped of metadata and kept
         *     beside any earlier photo (a project keeps up to five; none is overwritten).
         */
        post: operations["upload_source_photo_api_interior_projects__project_id__source_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/market/locations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Locations
         * @description Catalogue places by name with the headline of their latest published cohort.
         */
        get: operations["list_locations_api_market_locations_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/market/locations/{location_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Location
         * @description One place: live freshness and its latest cohort, one entry per cohort key.
         */
        get: operations["get_location_api_market_locations__location_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/market/locations/{location_id}/context": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Location Context
         * @description GUS BDL context of a place: hierarchy, per-metric value, trend, parent and peer comparison, sources.
         */
        get: operations["get_location_context_api_market_locations__location_id__context_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/market/locations/{location_id}/districts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Location Districts
         * @description The districts the source names under one place, with asking-rent statistics per district.
         *
         *     Computed from the place's own stored adverts; a place whose adverts carry no district answers
         *     `coverage: none` with an empty list, a district under the sufficiency threshold keeps its counts and
         *     withholds its statistics.
         */
        get: operations["get_location_districts_api_market_locations__location_id__districts_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/market/locations/{location_id}/history": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Location History
         * @description Daily history of one series and cohort, oldest first. A day without a published row is absent.
         */
        get: operations["get_location_history_api_market_locations__location_id__history_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/market/locations/{location_id}/ranking": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Location Ranking
         * @description The experimental locality index of the gmina a place belongs to: score, national and regional
         *     position with their denominators, every component with its value, year, unit and contribution, and the
         *     reasons when there is no score. Statistics about the area, never a property valuation.
         */
        get: operations["get_location_ranking_api_market_locations__location_id__ranking_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/market/overview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Overview
         * @description Every place this account may see, with its headline, what it maps to and its administrative area.
         *
         *     One answer for a map, a sort and a comparison. The free tier gets the fixed top list only.
         */
        get: operations["overview_api_market_overview_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/market/ranking": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Ranking Overview
         * @description Every place this account may see with the index of its gmina, best position first; a place that has
         *     no score (unmatched, ambiguous or too little data) is listed last with its state, never hidden.
         */
        get: operations["ranking_overview_api_market_ranking_get"];
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
        /**
         * List Saved
         * @description Newest first. `limit` may reach the per-account cap, so `limit=500` returns every saved listing.
         */
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
        /**
         * AnalysisState
         * @description Vision or OCR outcome, kept apart from storage: a stored photo stays viewable when analysis fails.
         * @enum {string}
         */
        AnalysisState: "not_requested" | "classified" | "failed";
        /**
         * AskingRentOut
         * @description One published aggregate: a series and cohort on one summary day.
         */
        AskingRentOut: {
            /**
             * Archive Days
             * @default 90
             * @constant
             */
            archive_days: 90;
            /**
             * As Of
             * Format: date-time
             */
            as_of: string;
            /** Backfilled */
            backfilled: boolean;
            /** Caveats */
            caveats: string[];
            /** Cohort Key */
            cohort_key: string;
            /** First Observed Count */
            first_observed_count: number | null;
            /**
             * Measure
             * @default original_asking_rent
             * @constant
             */
            measure: "original_asking_rent";
            /** Median Ppm2 */
            median_ppm2: string | null;
            /** Median Rent Pln */
            median_rent_pln: string | null;
            /** Observed Count */
            observed_count: number;
            /** P25 Ppm2 */
            p25_ppm2: string | null;
            /** P75 Ppm2 */
            p75_ppm2: string | null;
            /**
             * Price Basis
             * @default asking
             * @constant
             */
            price_basis: "asking";
            /** Priced Count */
            priced_count: number;
            /**
             * Series
             * @enum {string}
             */
            series: "additions" | "cohort";
            /**
             * Source
             * @default otodom
             * @constant
             */
            source: "otodom";
            /** Sufficient */
            sufficient: boolean;
            /**
             * Summary Date
             * Format: date
             */
            summary_date: string;
            /** Withheld Reason */
            withheld_reason: "insufficient_sample" | null;
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
            /** @description questions to ask the seller, generated with the report (RM-404); null when the audit has none stored (every audit made before RM-404, or no successful result) */
            seller_questions?: components["schemas"]["SellerQuestionBlock"] | null;
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
         * Availability
         * @enum {string}
         */
        Availability: "in_stock" | "out_of_stock" | "unknown";
        /**
         * Basket
         * @description Server-computed figures over the person's items. Not a room budget: delivery and missing items are
         *     not included, and `complete` only says every listed line has a price.
         */
        Basket: {
            /** Complete */
            complete: boolean;
            /**
             * Delivery Known Pln
             * @description delivery charges that are known; unknown ones are not zero
             */
            delivery_known_pln: string;
            /** Delivery Unknown Lines */
            delivery_unknown_lines: number;
            /** Known Subtotal Pln */
            known_subtotal_pln: string;
            /** Priced Lines */
            priced_lines: number;
            /**
             * Stale Lines
             * @description catalogue lines whose observed offer expired or cannot be bought
             */
            stale_lines: number;
            /** Unpriced Lines */
            unpriced_lines: number;
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
        /**
         * Brief
         * @description What the person wants. Saved on the project and snapshotted into every revision.
         */
        "Brief-Input": {
            /** Budget Pln */
            budget_pln?: number | string | null;
            /** Keep */
            keep?: string[];
            /** Notes */
            notes?: string | null;
            room_type: components["schemas"]["RoomType"];
            /** Style */
            style?: string | null;
        };
        /**
         * Brief
         * @description What the person wants. Saved on the project and snapshotted into every revision.
         */
        "Brief-Output": {
            /** Budget Pln */
            budget_pln?: string | null;
            /** Keep */
            keep?: string[];
            /** Notes */
            notes?: string | null;
            room_type: components["schemas"]["RoomType"];
            /** Style */
            style?: string | null;
        };
        /** CandidateOut */
        CandidateOut: {
            /** Flags */
            flags?: string[];
            offer: components["schemas"]["OfferOut"];
        };
        /** CatalogueStatus */
        CatalogueStatus: {
            /** Available */
            available: boolean;
            /**
             * Is Demo
             * @description true when the data is a deterministic demo, not a live merchant feed
             */
            is_demo: boolean;
            /** Provider */
            provider: string | null;
            /** Source Label */
            source_label: string | null;
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
        /**
         * CustomItemIn
         * @description The person's own item. Only `name` is required.
         */
        CustomItemIn: {
            /** Name */
            name: string;
            /** Price Pln */
            price_pln?: number | string | null;
            /**
             * Quantity
             * @default 1
             */
            quantity: number;
            /** Url */
            url?: string | null;
        };
        /** CustomItemOut */
        CustomItemOut: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Item Id
             * Format: uuid
             */
            item_id: string;
            /** Name */
            name: string;
            photo: components["schemas"]["MediaRef"] | null;
            /**
             * Price Pln
             * @description exact decimal string; null means the price is unknown
             */
            price_pln: string | null;
            /** Quantity */
            quantity: number;
            /** Url */
            url: string | null;
        };
        /**
         * DataStatus
         * @enum {string}
         */
        DataStatus: "unavailable" | "fresh" | "delayed" | "stale";
        /** Dimensions */
        Dimensions: {
            /** Depth Cm */
            depth_cm?: string | null;
            /** Height Cm */
            height_cm?: string | null;
            /** Source */
            source: string;
            /** Width Cm */
            width_cm?: string | null;
        };
        /**
         * DistrictOut
         * @description One district the source named under a place, over the same rolling cohort as the place's own series.
         *
         *     Statistics are withheld (null with a reason) under the sufficiency threshold; the counts stay. Nothing
         *     here is a share of the city's figures: it is what this district's own adverts say.
         */
        DistrictOut: {
            /** District Id */
            district_id: string;
            /** Median Ppm2 */
            median_ppm2: string | null;
            /** Median Rent Pln */
            median_rent_pln: string | null;
            /** Name */
            name: string;
            /** Observed Count */
            observed_count: number;
            /** P25 Ppm2 */
            p25_ppm2: string | null;
            /** P75 Ppm2 */
            p75_ppm2: string | null;
            /** Priced Count */
            priced_count: number;
            /** Sufficient */
            sufficient: boolean;
            /** Withheld Reason */
            withheld_reason: "insufficient_sample" | null;
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
        /** GenerationCreate */
        GenerationCreate: {
            /**
             * Revision Id
             * Format: uuid
             */
            revision_id: string;
        };
        /**
         * GenerationError
         * @description Stable reasons a generation ended `failed`; the SPA words them.
         * @enum {string}
         */
        GenerationError: "BUDGET_EXHAUSTED" | "NO_SOURCE_PHOTO" | "PROVIDER_REJECTED" | "PROVIDER_UNAVAILABLE" | "AMBIGUOUS" | "TIMEOUT" | "OUTPUT_REJECTED" | "STORAGE_FAILED" | "INTERNAL";
        /** GenerationOut */
        GenerationOut: {
            /** Cost Estimated */
            cost_estimated: boolean;
            /**
             * Cost Usd
             * @description provider-reported or, when estimated, the reserved amount
             */
            cost_usd: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            error_code: components["schemas"]["GenerationError"] | null;
            /** Finished At */
            finished_at: string | null;
            /**
             * Generation Id
             * Format: uuid
             */
            generation_id: string;
            /** Model */
            model: string;
            output: components["schemas"]["MediaRef"] | null;
            /** Prompt Version */
            prompt_version: string;
            /**
             * References Skipped
             * @description picked or own items whose photo was not sent (no photo or no right)
             */
            references_skipped: number;
            /**
             * References Used
             * @description photos sent to the model besides the room photo
             */
            references_used: number;
            /**
             * Revision Id
             * Format: uuid
             */
            revision_id: string;
            /** Started At */
            started_at: string | null;
            state: components["schemas"]["GenerationState"];
        };
        /**
         * GenerationState
         * @enum {string}
         */
        GenerationState: "queued" | "running" | "succeeded" | "failed" | "cancelled";
        /** GoogleCredential */
        GoogleCredential: {
            /** Credential */
            credential: string;
        };
        /**
         * ImageRights
         * @description What the source permits for a product photo; display, storage and generation are separate rights.
         */
        ImageRights: {
            /**
             * Cache
             * @default false
             */
            cache: boolean;
            /**
             * Display
             * @default true
             */
            display: boolean;
            /**
             * Generation Reference
             * @default false
             */
            generation_reference: boolean;
        };
        /** IndexCohortOut */
        IndexCohortOut: {
            /** Name Pl */
            name_pl: string;
            /** Of */
            of: number | null;
            /** Percentile */
            percentile: string | null;
            /** Rank */
            rank: number | null;
            /**
             * Scope
             * @enum {string}
             */
            scope: "national" | "voivodeship";
            /** Unit Name */
            unit_name: string | null;
        };
        /**
         * IndexComponentOut
         * @description One indicator inside the index: its value, where it stands among all gminas and what it adds.
         */
        IndexComponentOut: {
            /** Basis */
            basis: ("direct" | "proxy") | null;
            /** Explain Pl */
            explain_pl: string;
            /** Favourable Pl */
            favourable_pl: string;
            /** Key */
            key: string;
            measured: components["schemas"]["TerritoryOut"] | null;
            /** Metric Key */
            metric_key: string;
            /** Name Pl */
            name_pl: string;
            /** National Of */
            national_of: number | null;
            /** National Rank */
            national_rank: number | null;
            /** Pillar */
            pillar: string;
            /** Pillar Pl */
            pillar_pl: string;
            /** Points */
            points: string | null;
            /** Score */
            score: string | null;
            /** Unit Pl */
            unit_pl: string;
            /** Value */
            value: string | null;
            /** Weight */
            weight: number;
            /** Year */
            year: number | null;
        };
        /**
         * IndexOut
         * @description An experimental statistical summary of the gmina's official indicators, not a property metric.
         */
        IndexOut: {
            /** Caveat Pl */
            caveat_pl: string;
            /** Components */
            components: components["schemas"]["IndexComponentOut"][];
            gmina: components["schemas"]["TerritoryOut"] | null;
            /**
             * Higher Is Better
             * @default true
             * @constant
             */
            higher_is_better: true;
            /** Method Version */
            method_version: number;
            /** Min Cohort */
            min_cohort: number;
            /** Min Weight Coverage */
            min_weight_coverage: string;
            /** Missing */
            missing: string[];
            /** Newest Year */
            newest_year: number | null;
            /** Oldest Year */
            oldest_year: number | null;
            /** Positions */
            positions: components["schemas"]["IndexCohortOut"][];
            /** Reasons */
            reasons: string[];
            /** Score */
            score: string | null;
            /**
             * State
             * @enum {string}
             */
            state: "ok" | "scored_not_ranked" | "not_scored" | "no_data" | "unavailable";
            /** Title Pl */
            title_pl: string;
            /** Weight Coverage */
            weight_coverage: string | null;
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
         * ItemSnapshot
         * @description An item as it was when a revision was saved; later edits to the item do not change it.
         */
        ItemSnapshot: {
            /** Name */
            name: string;
            /** Photo Digest */
            photo_digest: string | null;
            /** Price Pln */
            price_pln: string | null;
            /** Quantity */
            quantity: number;
            /** Url */
            url: string | null;
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
        /** LocationContextOut */
        LocationContextOut: {
            /** Chain */
            chain: components["schemas"]["TerritoryOut"][];
            /** Location Id */
            location_id: string;
            mapping: components["schemas"]["PlaceMappingOut"];
            /** Metrics */
            metrics: components["schemas"]["MetricViewOut"][];
            /** Name */
            name: string;
            /** Published Metrics */
            published_metrics: number;
            source: components["schemas"]["SourceOut"];
        };
        /** LocationDetailOut */
        LocationDetailOut: {
            /** Cohort */
            cohort: components["schemas"]["AskingRentOut"][];
            /** Covered Until */
            covered_until: string | null;
            data_status: components["schemas"]["DataStatus"];
            /** Last Successful Refresh At */
            last_successful_refresh_at: string | null;
            /** Location Id */
            location_id: string;
            /** Name */
            name: string;
            /** Unresolved Gap Since */
            unresolved_gap_since: string | null;
            /** Usable For Ranking */
            usable_for_ranking: boolean;
        };
        /** LocationDistrictsOut */
        LocationDistrictsOut: {
            /**
             * As Of
             * Format: date-time
             */
            as_of: string;
            /** Caveats */
            caveats: string[];
            /** Cohort Key */
            cohort_key: string;
            /**
             * Coverage
             * @enum {string}
             */
            coverage: "supported" | "none";
            data_status: components["schemas"]["DataStatus"];
            /** Districts */
            districts: components["schemas"]["DistrictOut"][];
            /** Location Id */
            location_id: string;
            /** Name */
            name: string;
            /** Offers In Cohort */
            offers_in_cohort: number;
            /** Offers With District */
            offers_with_district: number;
            /**
             * Price Basis
             * @default asking
             * @constant
             */
            price_basis: "asking";
            /**
             * Source
             * @default otodom
             * @constant
             */
            source: "otodom";
        };
        /** LocationHistoryOut */
        LocationHistoryOut: {
            /** Cohort Key */
            cohort_key: string;
            /**
             * End
             * Format: date
             */
            end: string;
            /** Location Id */
            location_id: string;
            /** Points */
            points: components["schemas"]["AskingRentOut"][];
            /**
             * Series
             * @enum {string}
             */
            series: "additions" | "cohort";
            /**
             * Start
             * Format: date
             */
            start: string;
        };
        /** LocationIndexOut */
        LocationIndexOut: {
            index: components["schemas"]["IndexOut"];
            /** Location Id */
            location_id: string;
            mapping: components["schemas"]["PlaceMappingOut"];
            /** Name */
            name: string;
            source: components["schemas"]["SourceOut"];
        };
        /** LocationPage */
        LocationPage: {
            /** Items */
            items: components["schemas"]["LocationSummaryOut"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /** LocationSummaryOut */
        LocationSummaryOut: {
            data_status: components["schemas"]["DataStatus"];
            /** Last Successful Refresh At */
            last_successful_refresh_at: string | null;
            /** Latest Summary Date */
            latest_summary_date: string | null;
            /** Location Id */
            location_id: string;
            /** Median Ppm2 */
            median_ppm2: string | null;
            /** Median Rent Pln */
            median_rent_pln: string | null;
            /** Name */
            name: string;
            /** Priced Count */
            priced_count: number | null;
            /** Sufficient */
            sufficient: boolean | null;
            /** Withheld Reason */
            withheld_reason: "insufficient_sample" | null;
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
            /**
             * Has Password
             * @description Whether this account has an e-mail/password credential (a credential row exists). False for an account that only signs in with Google or a magic link; the SPA hides the change-password form for it.
             */
            has_password: boolean;
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
        /** MediaItem */
        MediaItem: {
            /** @default not_requested */
            analysis_state: components["schemas"]["AnalysisState"];
            /**
             * Content Digest
             * @description SHA-256 of the prepared bytes
             */
            content_digest?: string | null;
            /** Expires At */
            expires_at?: string | null;
            /** Failure Code */
            failure_code?: string | null;
            /** Height */
            height?: number | null;
            kind: components["schemas"]["MediaKind"];
            /**
             * Media Id
             * Format: uuid
             * @description Opaque and stable; vision output cites it
             */
            media_id?: string;
            mime?: components["schemas"]["MediaMime"] | null;
            /** Ordinal */
            ordinal: number;
            source_type: components["schemas"]["MediaSource"];
            /** @default pending */
            state: components["schemas"]["rm_contracts__media__MediaState"];
            /** Width */
            width?: number | null;
        };
        /**
         * MediaKind
         * @enum {string}
         */
        MediaKind: "photo" | "plan";
        /** MediaManifest */
        MediaManifest: {
            /**
             * Audit Id
             * Format: uuid
             */
            audit_id: string;
            /**
             * Created At
             * @description None while the manifest is empty
             */
            created_at?: string | null;
            /** Items */
            items: components["schemas"]["MediaItem"][];
            /**
             * Schema Version
             * @default 1
             */
            schema_version: number;
        };
        /**
         * MediaMime
         * @enum {string}
         */
        MediaMime: "image/jpeg" | "image/png" | "image/webp";
        /**
         * MediaPurpose
         * @enum {string}
         */
        MediaPurpose: "source" | "custom_item" | "render";
        /** MediaRef */
        MediaRef: {
            /** Content Digest */
            content_digest: string | null;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /** Height */
            height: number | null;
            /**
             * Media Id
             * Format: uuid
             */
            media_id: string;
            purpose: components["schemas"]["MediaPurpose"];
            state: components["schemas"]["rm_contracts__interior__MediaState"];
            /** Width */
            width: number | null;
        };
        /**
         * MediaSource
         * @enum {string}
         */
        MediaSource: "url" | "manual" | "upload";
        /** MetricViewOut */
        MetricViewOut: {
            /**
             * Direction
             * @enum {string}
             */
            direction: "higher_is_favorable" | "lower_is_favorable" | "neutral";
            /** Family */
            family: string;
            /** Family Pl */
            family_pl: string;
            /** Key */
            key: string;
            measured: components["schemas"]["TerritoryOut"] | null;
            /** Name Pl */
            name_pl: string;
            national: components["schemas"]["RankOut"] | null;
            /** Note Pl */
            note_pl: string;
            /** Parents */
            parents: components["schemas"]["ParentValueOut"][];
            peers: components["schemas"]["RankOut"] | null;
            /** Reason */
            reason: string | null;
            /** Release Id */
            release_id: string | null;
            /** Series */
            series: components["schemas"]["PointOut"][];
            /**
             * State
             * @enum {string}
             */
            state: "direct" | "proxy" | "unavailable";
            trend: components["schemas"]["TrendOut"] | null;
            /** Unit */
            unit: string;
            /** Value */
            value: string | null;
            /** Value Status */
            value_status: string | null;
            /** Year */
            year: number | null;
        };
        /**
         * OfferOut
         * @description An `Offer` as the API returns it: money as exact strings, plus the server-derived state.
         */
        OfferOut: {
            /** Attributes */
            attributes: {
                [key: string]: string;
            };
            availability: components["schemas"]["Availability"];
            /** Category */
            category: string;
            /** Delivery Known */
            delivery_known: boolean;
            /** Delivery Pln */
            delivery_pln: string | null;
            dimensions: components["schemas"]["Dimensions"] | null;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            image_rights: components["schemas"]["ImageRights"];
            /** Image Url */
            image_url: string | null;
            /**
             * Observed At
             * Format: date-time
             */
            observed_at: string;
            /** Offer Id */
            offer_id: string | null;
            /** Price Conditions */
            price_conditions: string | null;
            /** Price Is Gross */
            price_is_gross: boolean | null;
            /** Price Pln */
            price_pln: string | null;
            /** Product Id */
            product_id: string;
            /** Product Url */
            product_url: string;
            /** Provider */
            provider: string;
            /** Seller */
            seller: string;
            /** Source Label */
            source_label: string;
            state: components["schemas"]["OfferState"];
            /** Title */
            title: string;
            /** Variant Id */
            variant_id: string;
        };
        /**
         * OfferState
         * @description Derived on read from the clock and the stored observation; never stored.
         * @enum {string}
         */
        OfferState: "fresh" | "expired" | "unavailable";
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
        /** OverviewOut */
        OverviewOut: {
            /**
             * Access
             * @enum {string}
             */
            access: "full" | "free";
            /**
             * Cohort Key
             * @default all
             */
            cohort_key: string;
            /** Free Limit */
            free_limit: number;
            /** Free Rule Pl */
            free_rule_pl: string;
            /** Items */
            items: components["schemas"]["OverviewPlaceOut"][];
            /** Total Places */
            total_places: number;
            /** Visible Places */
            visible_places: number;
        };
        /**
         * OverviewPlaceOut
         * @description One place of the catalogue with what a map, a sort and a comparison need, from published data only.
         */
        OverviewPlaceOut: {
            data_status: components["schemas"]["DataStatus"];
            /** Gmina Teryt */
            gmina_teryt: string | null;
            /** Last Successful Refresh At */
            last_successful_refresh_at: string | null;
            /** Latest Summary Date */
            latest_summary_date: string | null;
            /** Location Id */
            location_id: string;
            /** Mapping */
            mapping: ("mapped" | "ambiguous" | "unmatched") | null;
            /** Median Ppm2 */
            median_ppm2: string | null;
            /** Median Rent Pln */
            median_rent_pln: string | null;
            /** Name */
            name: string;
            /** Powiat Name */
            powiat_name: string | null;
            /** Priced Count */
            priced_count: number | null;
            /** Relation */
            relation: ("gmina" | "within_gmina") | null;
            /** Sufficient */
            sufficient: boolean | null;
            /** Withheld Reason */
            withheld_reason: "insufficient_sample" | null;
            /** Wojewodztwo Name */
            wojewodztwo_name: string | null;
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
        /** ParentValueOut */
        ParentValueOut: {
            /** Relation */
            relation: ("above" | "below" | "equal") | null;
            territory: components["schemas"]["TerritoryOut"];
            /** Value */
            value: string | null;
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
        /** PlaceMappingOut */
        PlaceMappingOut: {
            /** Candidates */
            candidates: components["schemas"]["TerritoryOut"][];
            /** Method */
            method: string;
            /** Relation */
            relation: ("gmina" | "within_gmina") | null;
            /**
             * Status
             * @enum {string}
             */
            status: "mapped" | "ambiguous" | "unmatched";
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
            /**
             * Unlimited Reports
             * @description Explicit staff-granted entitlement: analyses are not charged and the whole Rynek opens.
             * @default false
             */
            unlimited_reports: boolean;
        };
        /** PointOut */
        PointOut: {
            /** Status */
            status: string;
            /** Value */
            value: string | null;
            /** Year */
            year: number;
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
        ProblemCode: "INVALID_LISTING_REF" | "QUOTA_EXHAUSTED" | "AUDIT_IN_PROGRESS" | "RENT_NOT_DEAL" | "FRACTIONAL_OWNERSHIP" | "LISTING_GONE" | "UPSTREAM_BLOCKED" | "UPSTREAM_SCHEMA_DRIFT" | "VISION_UNAVAILABLE" | "CONTEXT_UNAVAILABLE" | "INTERNAL" | "VALIDATION_ERROR" | "NOT_FOUND" | "HTTP_ERROR" | "NOT_READY" | "INVALID_GOOGLE_TOKEN" | "GOOGLE_EMAIL_UNVERIFIED" | "EMAIL_CONFIRMATION_REQUIRED" | "MAGIC_LINK_INVALID" | "INVALID_CREDENTIALS" | "WEAK_PASSWORD" | "AUTH_TOKEN_INVALID" | "ACCOUNT_EXISTS" | "BILLING_UNAVAILABLE" | "IDEMPOTENCY_CONFLICT" | "BILLING_PROVIDER_ERROR" | "INVALID_WEBHOOK_SIGNATURE" | "BILLING_HOLD" | "PURCHASE_NOT_REFUNDABLE" | "REFUND_NEEDS_REVIEW" | "EMAIL_NOT_VERIFIED" | "FEATURE_NOT_IN_PLAN" | "ADMIN_ONLY" | "ALREADY_SUBSCRIBED" | "INVALID_STRIPE_SIGNATURE" | "UNAUTHENTICATED" | "RATE_LIMITED" | "ORIGIN_NOT_ALLOWED" | "CONFIRMATION_MISMATCH" | "CREDIT_BELOW_ZERO" | "SAVED_LIMIT_REACHED" | "INTERIOR_LIMIT_REACHED" | "IMAGE_REJECTED" | "MEDIA_STORAGE_UNAVAILABLE" | "CATALOGUE_UNAVAILABLE" | "OFFER_UNAVAILABLE" | "GENERATION_UNAVAILABLE" | "GENERATION_CONFLICT";
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
        /** ProjectCreate */
        ProjectCreate: {
            brief: components["schemas"]["Brief-Input"];
            /** Name */
            name: string;
        };
        /** ProjectOut */
        ProjectOut: {
            basket: components["schemas"]["Basket"];
            brief: components["schemas"]["Brief-Output"];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /** Items */
            items: components["schemas"]["CustomItemOut"][];
            /** Name */
            name: string;
            /**
             * Project Id
             * Format: uuid
             */
            project_id: string;
            /** Revisions */
            revisions: components["schemas"]["RevisionOut"][];
            /** Selections */
            selections?: components["schemas"]["SelectionOut"][];
            source: components["schemas"]["MediaRef"] | null;
        };
        /** ProjectSummary */
        ProjectSummary: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /** Has Source */
            has_source: boolean;
            /** Name */
            name: string;
            /**
             * Project Id
             * Format: uuid
             */
            project_id: string;
            /** Revisions */
            revisions: number;
            room_type: components["schemas"]["RoomType"];
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
        /** RankOut */
        RankOut: {
            /** Coverage */
            coverage: string | null;
            /** Median */
            median: string | null;
            /** Of */
            of: number | null;
            /** Percentile */
            percentile: string | null;
            /** Rank */
            rank: number | null;
            /** Reasons */
            reasons: string[];
            /** Scope */
            scope: string;
            /**
             * Scope Level
             * @enum {string}
             */
            scope_level: "gmina" | "powiat" | "wojewodztwo" | "country";
            /**
             * State
             * @enum {string}
             */
            state: "ok" | "suppressed" | "unavailable";
        };
        /** RankingEntryOut */
        RankingEntryOut: {
            /** Gmina Name */
            gmina_name: string | null;
            /** Location Id */
            location_id: string;
            /** Name */
            name: string;
            /** Of */
            of: number | null;
            /** Rank */
            rank: number | null;
            /** Relation */
            relation: ("gmina" | "within_gmina") | null;
            /** Score */
            score: string | null;
            /**
             * State
             * @enum {string}
             */
            state: "ok" | "scored_not_ranked" | "not_scored" | "no_data" | "unavailable";
        };
        /** RankingOverviewOut */
        RankingOverviewOut: {
            /**
             * Access
             * @enum {string}
             */
            access: "full" | "free";
            /** Caveat Pl */
            caveat_pl: string;
            /** Cohort Name Pl */
            cohort_name_pl: string;
            /** Items */
            items: components["schemas"]["RankingEntryOut"][];
            /** Method Version */
            method_version: number;
            /** Scored Gminas */
            scored_gminas: number;
            source: components["schemas"]["SourceOut"];
            /** Title Pl */
            title_pl: string;
            /** Total Places */
            total_places: number;
            /** Visible Places */
            visible_places: number;
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
        /** RevisionOut */
        RevisionOut: {
            basket: components["schemas"]["Basket"];
            brief: components["schemas"]["Brief-Output"];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Items */
            items: components["schemas"]["ItemSnapshot"][];
            /** Number */
            number: number;
            /**
             * Revision Id
             * Format: uuid
             */
            revision_id: string;
            /** Selections */
            selections?: components["schemas"]["SelectionSnapshot"][];
            /** Source Digest */
            source_digest: string | null;
        };
        /**
         * RoomType
         * @enum {string}
         */
        RoomType: "living_room" | "bedroom" | "kitchen" | "bathroom" | "hallway" | "office" | "other";
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
         * SelectionIn
         * @description Pick an exact variant. The server re-fetches the offer from the provider; the client sends no price.
         */
        SelectionIn: {
            /** Product Id */
            product_id: string;
            /** Provider */
            provider: string;
            /**
             * Quantity
             * @default 1
             */
            quantity: number;
            /** Variant Id */
            variant_id: string;
        };
        /** SelectionOut */
        SelectionOut: {
            /**
             * Checked At
             * Format: date-time
             */
            checked_at: string;
            /**
             * Line Total Pln
             * @description quantity x price when the offer is fresh and priced, else null
             */
            line_total_pln: string | null;
            offer: components["schemas"]["OfferOut"];
            /** Quantity */
            quantity: number;
            /**
             * Selection Id
             * Format: uuid
             */
            selection_id: string;
        };
        /** SelectionQuantity */
        SelectionQuantity: {
            /** Quantity */
            quantity: number;
        };
        /**
         * SelectionSnapshot
         * @description A selection as a revision saw it.
         */
        SelectionSnapshot: {
            offer: components["schemas"]["OfferOut"];
            /** Quantity */
            quantity: number;
        };
        /**
         * SellerQuestion
         * @description A question to ask the seller (G-03, RM-404). Mirrors `deal_analyzer.seller_questions.SellerQuestion`;
         *     `tests/unit/test_seller_questions.py` fails if the two schemas drift.
         */
        SellerQuestion: {
            /**
             * Evidence
             * @description the facts it rests on; the engine never emits an empty list
             */
            evidence: string[];
            /**
             * Id
             * @description stable: rule plus evidence key
             */
            id: string;
            /** Reason */
            reason: string;
            /** @description stable rule code, for localisation in the SPA */
            rule: components["schemas"]["SellerQuestionRuleName"];
            /** Text */
            text: string;
        };
        /**
         * SellerQuestionBlock
         * @description The versioned block persisted with the audit. Null on audits made before RM-404: no questions.
         */
        SellerQuestionBlock: {
            /** Questions */
            questions: components["schemas"]["SellerQuestion"][];
            /** Version */
            version: number;
        };
        /**
         * SellerQuestionRuleName
         * @description Mirrors `deal_analyzer.seller_questions.SellerQuestionRule`; the drift test compares the values.
         * @enum {string}
         */
        SellerQuestionRuleName: "admin_fee_unknown" | "floor_unknown" | "build_year_unknown" | "condition_unclear" | "floor_plan_missing" | "seller_status_unclear" | "equipment_sale_status";
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
        /** SourceOut */
        SourceOut: {
            /** Attribution Pl */
            attribution_pl: string;
            /**
             * Name
             * @default GUS BDL
             * @constant
             */
            name: "GUS BDL";
            /** Note Pl */
            note_pl: string;
            /**
             * Url
             * @default https://bdl.stat.gov.pl
             */
            url: string;
        };
        /** TerritoryOut */
        TerritoryOut: {
            /**
             * Level
             * @enum {string}
             */
            level: "gmina" | "powiat" | "wojewodztwo" | "country";
            /** Name */
            name: string;
            /** Territory Id */
            territory_id: string;
            /** Teryt */
            teryt: string;
        };
        /** TrendOut */
        TrendOut: {
            /** Absolute Change */
            absolute_change: string | null;
            /** Comparable Steps */
            comparable_steps: number;
            /** Favorable */
            favorable: boolean | null;
            /** From Year */
            from_year: number | null;
            /** Movement */
            movement: ("up" | "down" | "flat") | null;
            /** Percent Change */
            percent_change: string | null;
            /** Reasons */
            reasons: string[];
            /**
             * State
             * @enum {string}
             */
            state: "ok" | "suppressed" | "unavailable";
            /** To Year */
            to_year: number | null;
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
        /**
         * MediaState
         * @enum {string}
         */
        rm_contracts__interior__MediaState: "pending" | "stored" | "failed";
        /**
         * MediaState
         * @description Storage state of the prepared image. `expired` is derived on read from `expires_at`.
         * @enum {string}
         */
        rm_contracts__media__MediaState: "pending" | "stored" | "rejected" | "failed" | "expired";
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
            /** @description Problem: HTTP_ERROR */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
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
            /** @description Problem: HTTP_ERROR */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
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
            /** @description Problem: HTTP_ERROR */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
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
            /** @description Problem: HTTP_ERROR */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
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
            /** @description Problem: HTTP_ERROR */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
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
            /** @description Problem: HTTP_ERROR */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
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
    read_media_manifest_api_audits__audit_id__media_get: {
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
                    "application/json": components["schemas"]["MediaManifest"];
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
            /** @description Problem: HTTP_ERROR */
            400: {
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
            /** @description Problem: HTTP_ERROR */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
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
            /** @description Problem: HTTP_ERROR */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
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
            /** @description Problem: HTTP_ERROR */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
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
            /** @description Problem: HTTP_ERROR */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
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
            /** @description Problem: HTTP_ERROR */
            400: {
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
            /** @description Problem: HTTP_ERROR */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
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
            /** @description Problem: HTTP_ERROR */
            400: {
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
            /** @description Problem: HTTP_ERROR */
            400: {
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
            /** @description Problem: HTTP_ERROR */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
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
            /** @description Problem: HTTP_ERROR */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
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
                /** @description The Idempotency-Key of a checkout: only the caller's purchase created with it (an empty list when it never arrived). Lets a client settle a lost answer without guessing. */
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
    catalogue_status_api_interior_catalogue_get: {
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
                    "application/json": components["schemas"]["CatalogueStatus"];
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
            /** @description Problem: FEATURE_NOT_IN_PLAN */
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
    demo_product_image_api_interior_catalogue_demo_image__product_id___variant_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                product_id: string;
                variant_id: string;
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
                    "image/png": string;
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
            /** @description Problem: FEATURE_NOT_IN_PLAN */
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
    list_projects_api_interior_projects_get: {
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
                    "application/json": components["schemas"]["ProjectSummary"][];
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
            /** @description Problem: FEATURE_NOT_IN_PLAN */
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
    create_project_api_interior_projects_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProjectCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectOut"];
                };
            };
            /** @description Problem: HTTP_ERROR */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
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
            /** @description Problem: FEATURE_NOT_IN_PLAN, ORIGIN_NOT_ALLOWED */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: INTERIOR_LIMIT_REACHED */
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
    get_project_api_interior_projects__project_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: string;
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
                    "application/json": components["schemas"]["ProjectOut"];
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
            /** @description Problem: FEATURE_NOT_IN_PLAN */
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
    update_project_api_interior_projects__project_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProjectCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectOut"];
                };
            };
            /** @description Problem: HTTP_ERROR */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
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
            /** @description Problem: FEATURE_NOT_IN_PLAN, ORIGIN_NOT_ALLOWED */
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
    delete_project_api_interior_projects__project_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: string;
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
            /** @description Problem: FEATURE_NOT_IN_PLAN, ORIGIN_NOT_ALLOWED */
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
    search_catalogue_api_interior_projects__project_id__catalogue_search_get: {
        parameters: {
            query?: {
                q?: string;
                category?: string | null;
                max_price_pln?: number | string | null;
                limit?: number;
            };
            header?: never;
            path: {
                project_id: string;
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
                    "application/json": components["schemas"]["CandidateOut"][];
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
            /** @description Problem: FEATURE_NOT_IN_PLAN */
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
            /** @description Problem: CATALOGUE_UNAVAILABLE, NOT_READY */
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
    list_generations_api_interior_projects__project_id__generations_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: string;
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
                    "application/json": components["schemas"]["GenerationOut"][];
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
            /** @description Problem: FEATURE_NOT_IN_PLAN */
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
    create_generation_api_interior_projects__project_id__generations_post: {
        parameters: {
            query?: never;
            header?: {
                /** @description A UUID per click. Repeating it returns the operation it created and never starts or pays for a second one; used for another revision it is 409 GENERATION_CONFLICT. */
                "Idempotency-Key"?: string | null;
            };
            path: {
                project_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GenerationCreate"];
            };
        };
        responses: {
            /** @description The same revision is already queued or running */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GenerationOut"];
                };
            };
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GenerationOut"];
                };
            };
            /** @description Problem: HTTP_ERROR */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
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
            /** @description Problem: FEATURE_NOT_IN_PLAN, ORIGIN_NOT_ALLOWED */
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
            /** @description Problem: GENERATION_CONFLICT */
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
            /** @description Problem: GENERATION_UNAVAILABLE, NOT_READY */
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
    get_generation_api_interior_projects__project_id__generations__generation_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: string;
                generation_id: string;
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
                    "application/json": components["schemas"]["GenerationOut"];
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
            /** @description Problem: FEATURE_NOT_IN_PLAN */
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
    cancel_generation_api_interior_projects__project_id__generations__generation_id__cancel_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: string;
                generation_id: string;
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
                    "application/json": components["schemas"]["GenerationOut"];
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
            /** @description Problem: FEATURE_NOT_IN_PLAN, ORIGIN_NOT_ALLOWED */
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
            /** @description Problem: GENERATION_CONFLICT */
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
    add_item_api_interior_projects__project_id__items_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CustomItemIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectOut"];
                };
            };
            /** @description Problem: HTTP_ERROR */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
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
            /** @description Problem: FEATURE_NOT_IN_PLAN, ORIGIN_NOT_ALLOWED */
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
            /** @description Problem: INTERIOR_LIMIT_REACHED */
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
    update_item_api_interior_projects__project_id__items__item_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: string;
                item_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CustomItemIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectOut"];
                };
            };
            /** @description Problem: HTTP_ERROR */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
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
            /** @description Problem: FEATURE_NOT_IN_PLAN, ORIGIN_NOT_ALLOWED */
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
    delete_item_api_interior_projects__project_id__items__item_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: string;
                item_id: string;
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
            /** @description Problem: FEATURE_NOT_IN_PLAN, ORIGIN_NOT_ALLOWED */
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
    upload_item_photo_api_interior_projects__project_id__items__item_id__photo_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: string;
                item_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/octet-stream": string;
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MediaRef"];
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
            /** @description Problem: FEATURE_NOT_IN_PLAN, ORIGIN_NOT_ALLOWED */
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
            /** @description Problem: IMAGE_REJECTED, VALIDATION_ERROR */
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
            /** @description Problem: MEDIA_STORAGE_UNAVAILABLE, NOT_READY */
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
    read_photo_api_interior_projects__project_id__media__media_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: string;
                media_id: string;
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
                    "image/jpeg": string;
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
            /** @description Problem: FEATURE_NOT_IN_PLAN */
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
            /** @description Problem: MEDIA_STORAGE_UNAVAILABLE, NOT_READY */
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
    create_revision_api_interior_projects__project_id__revisions_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectOut"];
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
            /** @description Problem: FEATURE_NOT_IN_PLAN, ORIGIN_NOT_ALLOWED */
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
    select_product_api_interior_projects__project_id__selections_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SelectionIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectOut"];
                };
            };
            /** @description Problem: HTTP_ERROR */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
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
            /** @description Problem: FEATURE_NOT_IN_PLAN, ORIGIN_NOT_ALLOWED */
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
            /** @description Problem: INTERIOR_LIMIT_REACHED, OFFER_UNAVAILABLE */
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
            /** @description Problem: CATALOGUE_UNAVAILABLE, NOT_READY */
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
    set_selection_quantity_api_interior_projects__project_id__selections__selection_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: string;
                selection_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SelectionQuantity"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectOut"];
                };
            };
            /** @description Problem: HTTP_ERROR */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
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
            /** @description Problem: FEATURE_NOT_IN_PLAN, ORIGIN_NOT_ALLOWED */
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
    delete_selection_api_interior_projects__project_id__selections__selection_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: string;
                selection_id: string;
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
            /** @description Problem: FEATURE_NOT_IN_PLAN, ORIGIN_NOT_ALLOWED */
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
    refresh_selection_api_interior_projects__project_id__selections__selection_id__refresh_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: string;
                selection_id: string;
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
                    "application/json": components["schemas"]["ProjectOut"];
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
            /** @description Problem: FEATURE_NOT_IN_PLAN, ORIGIN_NOT_ALLOWED */
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
            /** @description Problem: OFFER_UNAVAILABLE */
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
            /** @description Problem: CATALOGUE_UNAVAILABLE, NOT_READY */
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
    upload_source_photo_api_interior_projects__project_id__source_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/octet-stream": string;
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MediaRef"];
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
            /** @description Problem: FEATURE_NOT_IN_PLAN, ORIGIN_NOT_ALLOWED */
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
            /** @description Problem: INTERIOR_LIMIT_REACHED */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
                };
            };
            /** @description Problem: IMAGE_REJECTED, VALIDATION_ERROR */
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
            /** @description Problem: MEDIA_STORAGE_UNAVAILABLE, NOT_READY */
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
    list_locations_api_market_locations_get: {
        parameters: {
            query?: {
                /** @description part of the place name */
                q?: string | null;
                limit?: number;
                /** @description `next_cursor` of the previous page */
                cursor?: string | null;
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
                    "application/json": components["schemas"]["LocationPage"];
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
    get_location_api_market_locations__location_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description stable internal place id */
                location_id: string;
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
                    "application/json": components["schemas"]["LocationDetailOut"];
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
            /** @description Problem: FEATURE_NOT_IN_PLAN */
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
    get_location_context_api_market_locations__location_id__context_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description stable internal place id */
                location_id: string;
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
                    "application/json": components["schemas"]["LocationContextOut"];
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
            /** @description Problem: FEATURE_NOT_IN_PLAN */
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
    get_location_districts_api_market_locations__location_id__districts_get: {
        parameters: {
            query?: {
                /** @description apartment size or rooms cohort, `all` by default */
                cohort?: string;
            };
            header?: never;
            path: {
                /** @description stable internal place id */
                location_id: string;
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
                    "application/json": components["schemas"]["LocationDistrictsOut"];
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
            /** @description Problem: FEATURE_NOT_IN_PLAN */
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
    get_location_history_api_market_locations__location_id__history_get: {
        parameters: {
            query?: {
                /** @description `additions` and `cohort` are never mixed */
                series?: "additions" | "cohort";
                /** @description cohort key, `all` by default */
                cohort?: string;
                /** @description days ending today (UTC) */
                days?: number;
            };
            header?: never;
            path: {
                /** @description stable internal place id */
                location_id: string;
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
                    "application/json": components["schemas"]["LocationHistoryOut"];
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
            /** @description Problem: FEATURE_NOT_IN_PLAN */
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
    get_location_ranking_api_market_locations__location_id__ranking_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description stable internal place id */
                location_id: string;
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
                    "application/json": components["schemas"]["LocationIndexOut"];
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
            /** @description Problem: FEATURE_NOT_IN_PLAN */
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
    overview_api_market_overview_get: {
        parameters: {
            query?: {
                /** @description apartment size or rooms cohort, `all` by default */
                cohort?: string;
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
                    "application/json": components["schemas"]["OverviewOut"];
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
    ranking_overview_api_market_ranking_get: {
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
                    "application/json": components["schemas"]["RankingOverviewOut"];
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
            /** @description Problem: HTTP_ERROR */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
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
            /** @description Problem: HTTP_ERROR */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": components["schemas"]["Problem"];
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
