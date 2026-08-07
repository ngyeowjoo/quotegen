-- ============================================================================
-- BPO Quote Generator - Supabase schema
-- Run this ONCE in the Supabase SQL Editor (Project > SQL Editor > New query)
-- ============================================================================

-- ---------- ROLES & COUNTRY-SCOPED ACCESS ----------------------------------

create type app_role as enum ('admin', 'finance', 'hr', 'sales');

create table if not exists public.user_profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email text not null,
    full_name text,
    role app_role not null default 'sales',
    created_at timestamptz not null default now()
);

-- Which countries a Finance/HR user is allowed to EDIT master data for.
-- Sales/Admin ignore this table (Sales can't edit master data at all;
-- Admin can edit everything regardless of rows here).
create table if not exists public.user_country_access (
    user_id uuid not null references public.user_profiles(id) on delete cascade,
    country text not null,
    can_edit boolean not null default true,
    primary key (user_id, country)
);

-- ---------- MASTER DATA ------------------------------------------------------

create table if not exists public.countries_drivers (
    id bigint generated always as identity primary key,
    biz_unit text,
    country text not null,
    city text not null unique,
    paid_hrs numeric,
    logged_hrs numeric,
    productive_hrs numeric,
    log_shrinkage numeric,
    prod_shrinkage numeric,
    monthly_attrition numeric,
    annual_wage_inflation numeric,
    staff_tenure_months numeric,
    social_security_pct numeric,
    night_premium numeric,
    night_allowance_lc numeric,
    shared_services_lc numeric,
    it_telecom_lc numeric,
    facilities_lc numeric,
    general_overheads_lc numeric,
    total_overheads_lc numeric,
    hoops text,
    updated_at timestamptz not null default now(),
    updated_by uuid references public.user_profiles(id)
);

create table if not exists public.base_salary_db (
    id bigint generated always as identity primary key,
    campaign_type text not null,
    role text not null,
    native_flag text,
    city text not null,
    base_salary numeric not null,
    updated_at timestamptz not null default now(),
    updated_by uuid references public.user_profiles(id),
    unique (campaign_type, role, native_flag, city)
);

create table if not exists public.overheads (
    id bigint generated always as identity primary key,
    overhead_mode text not null unique,
    shared_services numeric,
    it_telecom numeric,
    facilities numeric,
    general_overheads numeric,
    total_overheads numeric,
    updated_at timestamptz not null default now(),
    updated_by uuid references public.user_profiles(id)
);

create table if not exists public.fx_rates (
    id bigint generated always as identity primary key,
    currency text not null unique,
    rate_per_usd numeric not null,
    updated_at timestamptz not null default now(),
    updated_by uuid references public.user_profiles(id)
);

create table if not exists public.tax_rates (
    id bigint generated always as identity primary key,
    country text not null,
    biz_unit text,
    currency text,
    vat_pct numeric,
    social_security_pct numeric,
    updated_at timestamptz not null default now(),
    updated_by uuid references public.user_profiles(id),
    unique (country, biz_unit)
);

create table if not exists public.campaign_types (
    id bigint generated always as identity primary key,
    display_name text not null unique,
    key text not null unique,
    description text
);

create table if not exists public.span_ratios (
    id bigint generated always as identity primary key,
    lob text not null unique,
    fully_loaded_addon numeric,
    staff_cost_component numeric,
    overhead_component numeric,
    penalty_component numeric,
    margin_component numeric,
    updated_at timestamptz not null default now(),
    updated_by uuid references public.user_profiles(id)
);

create table if not exists public.commercial_terms (
    id bigint generated always as identity primary key,
    version int not null,
    body text not null,
    created_at timestamptz not null default now(),
    created_by uuid references public.user_profiles(id)
);

-- ---------- QUOTES -----------------------------------------------------------

create table if not exists public.quotes (
    id uuid primary key default gen_random_uuid(),
    client_name text not null,
    project_name text,
    quote_currency text not null,
    margin_pct numeric not null,
    penalty_pct numeric not null default 0,
    overhead_mode text not null,
    fully_loaded boolean not null default true,
    include_vat boolean not null default false,
    hours_basis text not null default 'productive',
    status text not null default 'draft',
    created_by uuid references public.user_profiles(id),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.quote_line_items (
    id bigint generated always as identity primary key,
    quote_id uuid not null references public.quotes(id) on delete cascade,
    city text not null,
    campaign_type text not null,
    role text not null,
    shift text not null,
    fte_ordered numeric not null,
    contingency_fte numeric not null default 0,
    final_monthly_rate numeric,
    hourly_rate numeric,
    monthly_total numeric,
    calc_breakdown jsonb,  -- full RoleQuoteResult, for auditability
    created_at timestamptz not null default now()
);

-- ============================================================================
-- ROW LEVEL SECURITY
-- ============================================================================

alter table public.user_profiles enable row level security;
alter table public.user_country_access enable row level security;
alter table public.countries_drivers enable row level security;
alter table public.base_salary_db enable row level security;
alter table public.overheads enable row level security;
alter table public.fx_rates enable row level security;
alter table public.tax_rates enable row level security;
alter table public.campaign_types enable row level security;
alter table public.span_ratios enable row level security;
alter table public.commercial_terms enable row level security;
alter table public.quotes enable row level security;
alter table public.quote_line_items enable row level security;

-- Helper: current user's role
create or replace function public.current_role() returns app_role
language sql stable security definer as $$
    select role from public.user_profiles where id = auth.uid();
$$;

-- Helper: does current user have edit access to a given country?
create or replace function public.can_edit_country(target_country text) returns boolean
language sql stable security definer as $$
    select
        public.current_role() = 'admin'
        or exists (
            select 1 from public.user_country_access
            where user_id = auth.uid() and country = target_country and can_edit = true
        );
$$;

-- Everyone logged in can READ all master data (needed to build quotes)
create policy "read master data - drivers" on public.countries_drivers for select using (auth.uid() is not null);
create policy "read master data - salary" on public.base_salary_db for select using (auth.uid() is not null);
create policy "read master data - overheads" on public.overheads for select using (auth.uid() is not null);
create policy "read master data - fx" on public.fx_rates for select using (auth.uid() is not null);
create policy "read master data - tax" on public.tax_rates for select using (auth.uid() is not null);
create policy "read master data - campaign types" on public.campaign_types for select using (auth.uid() is not null);
create policy "read master data - span ratios" on public.span_ratios for select using (auth.uid() is not null);
create policy "read master data - commercial terms" on public.commercial_terms for select using (auth.uid() is not null);

-- Only HR can write base_salary_db, scoped to their granted countries
-- (country for base_salary_db is via city -> countries_drivers.country lookup)
create policy "hr write salary" on public.base_salary_db for all
    using (
        public.current_role() = 'admin'
        or (
            public.current_role() = 'hr'
            and exists (
                select 1 from public.countries_drivers cd
                where cd.city = base_salary_db.city
                and public.can_edit_country(cd.country)
            )
        )
    );

-- Only Finance can write overheads / fx_rates / tax_rates
create policy "finance write overheads" on public.overheads for all
    using (public.current_role() in ('admin', 'finance'));

create policy "finance write fx" on public.fx_rates for all
    using (public.current_role() in ('admin', 'finance'));

create policy "finance write tax scoped" on public.tax_rates for all
    using (
        public.current_role() = 'admin'
        or (public.current_role() = 'finance' and public.can_edit_country(tax_rates.country))
    );

create policy "finance write drivers scoped" on public.countries_drivers for all
    using (
        public.current_role() = 'admin'
        or (public.current_role() = 'finance' and public.can_edit_country(countries_drivers.country))
    );

-- Admin only: campaign types, span ratios, commercial terms
create policy "admin write campaign types" on public.campaign_types for insert with check (public.current_role() = 'admin');
create policy "admin update campaign types" on public.campaign_types for update using (public.current_role() = 'admin');
create policy "admin delete campaign types" on public.campaign_types for delete using (public.current_role() = 'admin');

create policy "admin write span ratios" on public.span_ratios for all using (public.current_role() = 'admin');
create policy "admin write commercial terms" on public.commercial_terms for all using (public.current_role() = 'admin');

-- user_profiles: users can read their own row; admin can read/write all
create policy "read own profile" on public.user_profiles for select using (auth.uid() = id or public.current_role() = 'admin');
create policy "admin manage profiles" on public.user_profiles for all using (public.current_role() = 'admin');

create policy "read own country access" on public.user_country_access for select using (auth.uid() = user_id or public.current_role() = 'admin');
create policy "admin manage country access" on public.user_country_access for all using (public.current_role() = 'admin');

-- Quotes: any logged-in user (sales/admin/finance) can create quotes and see/edit their own;
-- admin sees all.
create policy "own quotes read" on public.quotes for select using (created_by = auth.uid() or public.current_role() = 'admin');
create policy "own quotes insert" on public.quotes for insert with check (created_by = auth.uid());
create policy "own quotes update" on public.quotes for update using (created_by = auth.uid() or public.current_role() = 'admin');
create policy "own quotes delete" on public.quotes for delete using (created_by = auth.uid() or public.current_role() = 'admin');

create policy "own quote lines read" on public.quote_line_items for select using (
    exists (select 1 from public.quotes q where q.id = quote_line_items.quote_id and (q.created_by = auth.uid() or public.current_role() = 'admin'))
);
create policy "own quote lines write" on public.quote_line_items for all using (
    exists (select 1 from public.quotes q where q.id = quote_line_items.quote_id and (q.created_by = auth.uid() or public.current_role() = 'admin'))
);

-- ---------- Auto-create a user_profiles row when someone signs up ----------
create or replace function public.handle_new_user() returns trigger
language plpgsql security definer as $$
begin
    insert into public.user_profiles (id, email, role)
    values (new.id, new.email, 'sales');
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute procedure public.handle_new_user();
