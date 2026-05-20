import io
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether,
)
from reportlab.platypus.flowables import Flowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Line, Rect, String, Path, Circle
from reportlab.graphics import renderPDF
from reportlab.pdfbase import pdfmetrics

W, H = A4
MARGIN = 18 * mm

NAVY       = colors.HexColor('#1a1f36')
BLUE       = colors.HexColor('#3498db')
MID_BLUE   = colors.HexColor('#2c3e6b')
GREEN      = colors.HexColor('#27ae60')
ORANGE     = colors.HexColor('#e67e22')
RED        = colors.HexColor('#e74c3c')
PURPLE     = colors.HexColor('#9b59b6')
TEAL       = colors.HexColor('#1abc9c')
DARK_GRAY  = colors.HexColor('#2c3e50')
MID_GRAY   = colors.HexColor('#7f8c8d')
LIGHT_GRAY = colors.HexColor('#ecf0f1')
RULE_GRAY  = colors.HexColor('#dee2e6')
TEXT_DARK  = colors.HexColor('#0f172a')
TEXT_MID   = colors.HexColor('#334155')
TEXT_LIGHT = colors.HexColor('#64748b')
BG_ROW     = colors.HexColor('#f8fafc')

METRIC_COLORS = {
    'health':       colors.HexColor('#27ae60'),
    'roll':         colors.HexColor('#9b59b6'),
    'pitch':        colors.HexColor('#3498db'),
    'yaw':          colors.HexColor('#1abc9c'),
    'temp':         colors.HexColor('#e67e22'),
    'tempVariance': colors.HexColor('#e74c3c'),
    'reflectivity': colors.HexColor('#16a085'),
    'confidence':   colors.HexColor('#8e44ad'),
    'range':        colors.HexColor('#2980b9'),
    'velocity':     colors.HexColor('#f39c12'),
    'deltaV':       colors.HexColor('#6c3483'),
    'manConf':      colors.HexColor('#7f8c8d'),
    'drift':        colors.HexColor('#e67e22'),
    'perigee':      colors.HexColor('#1a252f'),
    'spin':         colors.HexColor('#2c3e50'),
    'mass':         colors.HexColor('#7f8c8d'),
}


def _build_chart_data(observations: list[dict]) -> list[dict]:
    sorted_obs = sorted(observations, key=lambda o: o.get('observation_epoch') or '')
    rows = []
    for obs in sorted_obs:
        att = obs.get('attitude') or {}
        thermal = obs.get('thermal') or {}
        mat = obs.get('material_signature') or {}
        prox = obs.get('proximity_state') or {}
        man = obs.get('maneuver_indicator') or {}
        orb = obs.get('orbital_decay_indicator') or {}
        sf = att.get('stability_flag')
        is_unstable = None
        if sf is not None:
            is_unstable = sf if isinstance(sf, bool) else sf != 'nominal'
        man_raw = man.get('maneuver_flag')
        man_flag_src = obs.get('maneuver_flag')
        man_val = man_flag_src if man_flag_src is not None else man_raw
        man_flag = None
        if man_val is not None:
            man_flag = man_val not in (False, 'false')
        rows.append({
            'epoch':            obs.get('observation_epoch'),
            'health':           obs.get('derived_health_score'),
            'roll':             att.get('roll_deg'),
            'pitch':            att.get('pitch_deg'),
            'yaw':              att.get('yaw_deg'),
            'isUnstable':       is_unstable,
            'temp':             obs.get('surface_temp_K') or thermal.get('surface_temp_K'),
            'tempVariance':     obs.get('surface_temp_variance_30d') or thermal.get('temp_variance_30d'),
            'thermalAnomaly':   thermal.get('anomaly_flag'),
            'reflectivity':     mat.get('reflectivity_index'),
            'materialConfidence': mat.get('material_confidence'),
            'range':            prox.get('range_km'),
            'velocity':         prox.get('relative_velocity_ms'),
            'deltaV':           man.get('delta_v_residual_ms'),
            'manConf':          man.get('maneuver_confidence'),
            'manFlag':          man_flag,
            'drift':            orb.get('perigee_drift_km_per_day'),
            'estimatedPerigee': orb.get('estimated_perigee_km'),
            'mass':             obs.get('estimated_mass_kg'),
            'spin':             obs.get('spin_rate_rpm'),
            'passId':           obs.get('pass_id'),
            'illumination':     obs.get('illumination'),
        })
    return rows


def _fmt_dt(iso: str | None) -> str:
    if not iso:
        return '—'
    return iso[:16].replace('T', ' ') + ' UTC'


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return '—'
    return iso[:10]


def _fmt_val(v) -> str:
    if v is None:
        return '—'
    if isinstance(v, float):
        if abs(v) >= 10000:
            return f'{v/1000:.1f}k'
        if abs(v) >= 1000:
            return f'{v:.0f}'
        if abs(v) >= 100:
            return f'{v:.1f}'
        if abs(v) >= 10:
            return f'{v:.2f}'
        return f'{v:.3f}'
    return str(v)


def _nice_range(vals: list) -> tuple[float, float]:
    valid = [v for v in vals if v is not None and isinstance(v, (int, float))]
    if not valid:
        return 0.0, 1.0
    mn, mx = min(valid), max(valid)
    if mn == mx:
        pad = abs(mn) * 0.1 or 1.0
        return mn - pad, mx + pad
    pad = (mx - mn) * 0.05
    return mn - pad, mx + pad


def _nice_ticks(mn: float, mx: float, count: int = 5) -> list[float]:
    step = (mx - mn) / (count - 1)
    return [mn + step * i for i in range(count)]


class _LineChart(Flowable):
    """A compact SVG-like line chart drawn with reportlab graphics."""

    def __init__(
        self,
        data: list[dict],
        left_metrics: list[dict],
        right_metrics: list[dict] | None = None,
        fixed_range: dict | None = None,
        fill_under: bool = False,
        flags: list[dict] | None = None,
        chart_width: float = 440,
        chart_height: float = 90,
    ):
        super().__init__()
        self.data = data
        self.left_metrics = [m for m in left_metrics if not m.get('tbd')]
        self.right_metrics = [m for m in (right_metrics or []) if not m.get('tbd')]
        self.fixed_range = fixed_range
        self.fill_under = fill_under
        self.flags = [f for f in (flags or []) if not f.get('tbd')]
        self.chart_width = chart_width
        self.chart_height = chart_height
        self.width = chart_width
        self.height = chart_height

    def draw(self):
        d = self.data
        n = len(d)
        if n == 0:
            return

        pad = {'top': 12, 'right': 60, 'bottom': 26, 'left': 52}
        if not self.right_metrics:
            pad['right'] = 14
        iw = self.chart_width - pad['left'] - pad['right']
        ih = self.chart_height - pad['top'] - pad['bottom']

        def xpx(i):
            if n <= 1:
                return pad['left'] + iw / 2
            return pad['left'] + (i / (n - 1)) * iw

        l_vals = [d[i].get(m['key']) for m in self.left_metrics for i in range(n)]
        if self.fixed_range:
            l_min, l_max = self.fixed_range['min'], self.fixed_range['max']
        else:
            l_min, l_max = _nice_range(l_vals)
        l_ticks = _nice_ticks(l_min, l_max)

        r_min, r_max = 0.0, 1.0
        r_ticks = []
        if self.right_metrics:
            r_vals = [d[i].get(m['key']) for m in self.right_metrics for i in range(n)]
            r_min, r_max = _nice_range(r_vals)
            r_ticks = _nice_ticks(r_min, r_max)

        def yl(v):
            if v is None:
                return None
            return pad['bottom'] + ((v - l_min) / (l_max - l_min)) * ih if l_max != l_min else pad['bottom'] + ih / 2

        def yr(v):
            if v is None:
                return None
            return pad['bottom'] + ((v - r_min) / (r_max - r_min)) * ih if r_max != r_min else pad['bottom'] + ih / 2

        c = self.canv

        c.setStrokeColor(RULE_GRAY)
        c.setLineWidth(0.4)
        for t in l_ticks:
            y = yl(t)
            c.line(pad['left'], y, pad['left'] + iw, y)

        c.setFont('Helvetica', 6)
        c.setFillColor(self.left_metrics[0]['color'] if self.left_metrics else MID_GRAY)
        for t in l_ticks:
            y = yl(t)
            lbl = _fmt_val(t)
            c.drawRightString(pad['left'] - 3, y - 2, lbl)

        if self.right_metrics:
            c.setFillColor(self.right_metrics[0]['color'])
            for t in r_ticks:
                y = yr(t)
                lbl = _fmt_val(t)
                c.drawString(pad['left'] + iw + 3, y - 2, lbl)
            c.setStrokeColor(RULE_GRAY)
            c.setLineWidth(0.5)
            c.line(pad['left'] + iw, pad['bottom'], pad['left'] + iw, pad['bottom'] + ih)

        label_step = max(1, n // 10)
        c.setFont('Helvetica', 5.5)
        c.setFillColor(MID_GRAY)
        for i, row in enumerate(d):
            if i % label_step != 0 and i != n - 1:
                continue
            ep = row.get('epoch') or ''
            lbl = ep[5:10] if ep else ''
            if lbl:
                c.drawCentredString(xpx(i), pad['bottom'] - 9, lbl)

        c.setStrokeColor(RULE_GRAY)
        c.setLineWidth(0.8)
        c.line(pad['left'], pad['bottom'], pad['left'], pad['bottom'] + ih)
        c.line(pad['left'], pad['bottom'], pad['left'] + iw, pad['bottom'])

        for flag in self.flags:
            if flag.get('style') != 'line':
                continue
            fc = colors.HexColor(flag['trueColor']) if isinstance(flag['trueColor'], str) else flag['trueColor']
            c.setStrokeColor(fc)
            c.setLineWidth(1.2)
            c.setDash([3, 3])
            for i, row in enumerate(d):
                v = row.get(flag['key'])
                if not v or (flag.get('trueOnly') and v is not True):
                    continue
                x = xpx(i)
                c.line(x, pad['bottom'], x, pad['bottom'] + ih)
            c.setDash([])

        if self.fill_under and self.left_metrics:
            primary = self.left_metrics[0]
            pts = [(xpx(i), yl(row.get(primary['key']))) for i, row in enumerate(d) if yl(row.get(primary['key'])) is not None]
            if len(pts) >= 2:
                path = c.beginPath()
                path.moveTo(pts[0][0], pts[0][1])
                for px, py in pts[1:]:
                    path.lineTo(px, py)
                path.lineTo(pts[-1][0], pad['bottom'])
                path.lineTo(pts[0][0], pad['bottom'])
                path.close()
                col = primary['color']
                if isinstance(col, str):
                    col = colors.HexColor(col)
                r, g, b = col.red, col.green, col.blue
                c.setFillColorRGB(r, g, b, 0.12)
                c.drawPath(path, fill=1, stroke=0)

        for idx, metric in enumerate(self.left_metrics):
            mc = metric['color']
            if isinstance(mc, str):
                mc = colors.HexColor(mc)
            c.setStrokeColor(mc)
            c.setLineWidth(1.6 if idx == 0 else 1.2)
            pts = [(xpx(i), yl(row.get(metric['key']))) for i, row in enumerate(d)]
            pts = [(x, y) for x, y in pts if y is not None]
            if len(pts) >= 2:
                p = c.beginPath()
                p.moveTo(*pts[0])
                for px, py in pts[1:]:
                    p.lineTo(px, py)
                c.drawPath(p, fill=0, stroke=1)

        for idx, metric in enumerate(self.right_metrics):
            mc = metric['color']
            if isinstance(mc, str):
                mc = colors.HexColor(mc)
            c.setStrokeColor(mc)
            c.setLineWidth(1.2)
            c.setDash([4, 2])
            pts = [(xpx(i), yr(row.get(metric['key']))) for i, row in enumerate(d)]
            pts = [(x, y) for x, y in pts if y is not None]
            if len(pts) >= 2:
                p = c.beginPath()
                p.moveTo(*pts[0])
                for px, py in pts[1:]:
                    p.lineTo(px, py)
                c.drawPath(p, fill=0, stroke=1)
            c.setDash([])


class _CoverHeader(Flowable):
    def __init__(self, task_number: str, status: str, generated_at: str, width: float):
        super().__init__()
        self.task_number = task_number
        self.status = status
        self.generated_at = generated_at
        self.width = width
        self.height = 42 * mm

    def draw(self):
        c = self.canv
        h = self.height

        c.setFillColor(NAVY)
        c.rect(0, 0, self.width, h, fill=1, stroke=0)

        c.setFillColor(MID_BLUE)
        c.rect(0, 0, self.width * 0.35, h, fill=1, stroke=0)

        c.setFillColor(colors.white)
        c.setFont('Helvetica-Bold', 22)
        c.drawString(10 * mm, h - 15 * mm, 'OBSERVATION REPORT')

        c.setFont('Helvetica', 9)
        c.setFillColorRGB(1, 1, 1, 0.65)
        c.drawString(10 * mm, h - 22 * mm, 'TALON Space Intelligence Platform')

        c.setFont('Helvetica-Bold', 13)
        c.setFillColor(colors.white)
        c.drawRightString(self.width - 10 * mm, h - 13 * mm, self.task_number)

        c.setFont('Helvetica', 8)
        c.setFillColorRGB(1, 1, 1, 0.75)
        c.drawRightString(self.width - 10 * mm, h - 20 * mm, f'Status: {self.status}')
        c.drawRightString(self.width - 10 * mm, h - 27 * mm, f'Generated: {self.generated_at}')


class _SectionHeader(Flowable):
    def __init__(self, title: str, width: float):
        super().__init__()
        self.title = title
        self.width = width
        self.height = 8 * mm

    def draw(self):
        c = self.canv
        c.setFillColor(NAVY)
        c.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont('Helvetica-Bold', 9)
        c.drawString(4 * mm, 2.8 * mm, self.title.upper())


def _stat_table(pairs: list[tuple[str, str]], body_width: float = 494) -> Table:
    lbl_style = ParagraphStyle(
        'st_lbl', fontName='Helvetica-Bold', fontSize=7.5,
        textColor=TEXT_LIGHT, leading=10,
    )
    val_style = ParagraphStyle(
        'st_val', fontName='Helvetica', fontSize=8,
        textColor=TEXT_DARK, leading=10,
    )

    chunk_size = 2
    data = []
    for i in range(0, len(pairs), chunk_size):
        chunk = pairs[i:i + chunk_size]
        row = []
        for label, value in chunk:
            row.append(Paragraph(label, lbl_style))
            row.append(Paragraph(value, val_style))
        while len(row) < chunk_size * 2:
            row.extend([Paragraph('', lbl_style), Paragraph('', val_style)])
        data.append(row)

    lw = body_width * 0.21
    vw = body_width * 0.29
    col_widths = [lw, vw, lw, vw]

    style = TableStyle([
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [BG_ROW, colors.white]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.3, RULE_GRAY),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEAFTER', (1, 0), (1, -1), 0.8, RULE_GRAY),
    ])
    return Table(data, colWidths=col_widths, style=style)


def _make_table(headers: list[str], rows: list[list], col_widths: list[float] | None = None) -> Table:
    header_row = [Paragraph(h, ParagraphStyle('th', fontName='Helvetica-Bold', fontSize=7,
                                               textColor=TEXT_LIGHT, leading=9)) for h in headers]
    table_rows = [header_row]
    for row in rows:
        table_rows.append([
            Paragraph(str(cell) if cell is not None else '—',
                      ParagraphStyle('td', fontName='Helvetica', fontSize=7.5,
                                     textColor=TEXT_DARK, leading=10))
            for cell in row
        ])
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BG_ROW),
        ('LINEBELOW', (0, 0), (-1, 0), 0.8, RULE_GRAY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BG_ROW]),
        ('GRID', (0, 0), (-1, -1), 0.3, RULE_GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ])
    return Table(table_rows, colWidths=col_widths, style=style, repeatRows=1)


def generate_task_report(task: dict, observations: list[dict]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )

    styles = getSampleStyleSheet()
    body_w = W - 2 * MARGIN

    normal = ParagraphStyle('normal', fontName='Helvetica', fontSize=8.5, textColor=TEXT_MID, leading=12)
    h2 = ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=11, textColor=TEXT_DARK, leading=14, spaceBefore=6)
    small_gray = ParagraphStyle('sg', fontName='Helvetica', fontSize=7, textColor=TEXT_LIGHT, leading=9)
    legend_style = ParagraphStyle('leg', fontName='Helvetica', fontSize=7, textColor=TEXT_MID, leading=9)

    chart_data = _build_chart_data(observations)

    now = datetime.now(timezone.utc)
    generated_at = now.strftime('%Y-%m-%d %H:%M UTC')

    task_number = task.get('task_number') or task.get('_key') or '—'
    customer_status = task.get('customer_status') or task.get('status') or '—'
    norad_id = task.get('target_norad_id')
    scope = task.get('scope') or {}
    sla = task.get('sla') or {}
    commercial = task.get('commercial') or {}
    if not commercial and task.get('quote'):
        commercial = {'fee_amount': task['quote'].get('amount_usd'), 'currency': 'USD'}

    health_vals = [r['health'] for r in chart_data if r.get('health') is not None]
    avg_health = sum(health_vals) / len(health_vals) if health_vals else None
    min_health = min(health_vals) if health_vals else None
    anomaly_count = sum(1 for r in chart_data if r.get('thermalAnomaly') is True)
    maneuver_count = sum(1 for r in chart_data if r.get('manFlag') is True)
    obs_count = len(observations)
    date_from = chart_data[0].get('epoch', '')[:10] if chart_data else '—'
    date_to = chart_data[-1].get('epoch', '')[:10] if chart_data else '—'

    story = []

    story.append(_CoverHeader(task_number, customer_status, generated_at, body_w))
    story.append(Spacer(1, 6 * mm))

    story.append(_SectionHeader('Executive Summary', body_w))
    story.append(Spacer(1, 3 * mm))

    summary_pairs = [
        ('Task Number', task_number),
        ('Status', customer_status),
        ('Priority', (task.get('priority') or '—').capitalize()),
        ('Target NORAD ID', str(norad_id) if norad_id is not None else '—'),
        ('Time Window Start', _fmt_dt(scope.get('time_window_start'))),
        ('Time Window End', _fmt_dt(scope.get('time_window_end'))),
        ('Total Observations', str(obs_count)),
        ('Observation Range', f'{date_from} → {date_to}' if date_from != '—' else '—'),
        ('Avg Health Score', f'{avg_health:.1f}' if avg_health is not None else '—'),
        ('Min Health Score', f'{min_health:.1f}' if min_health is not None else '—'),
        ('Thermal Anomalies', str(anomaly_count)),
        ('Maneuver Flags', str(maneuver_count)),
    ]

    story.append(_stat_table(summary_pairs, body_width=body_w))
    story.append(Spacer(1, 5 * mm))

    story.append(_SectionHeader('Task Scope & Commercial Details', body_w))
    story.append(Spacer(1, 3 * mm))

    scope_pairs = [
        ('Obs. Count Min', str(scope.get('observation_count_min') or '—')),
        ('Obs. Count Max', str(scope.get('observation_count_max') or '—')),
        ('Sensor Types', ', '.join(scope.get('required_sensor_types') or []) or '—'),
        ('Maneuver Auth.', 'Yes' if scope.get('maneuver_authorised') else 'No' if scope.get('maneuver_authorised') is False else '—'),
        ('Min Indep. Score', str(scope.get('min_independence_score') or '—')),
        ('Delivery Due', _fmt_date(sla.get('delivery_due'))),
        ('QA Window (days)', str(sla.get('qa_window_days') or '—')),
        ('Fee', f'{commercial.get("fee_amount")} {commercial.get("currency", "")}' if commercial.get('fee_amount') is not None else '—'),
        ('Billing', str(commercial.get('billing') or '—')),
        ('PO Reference', str(commercial.get('po_reference') or '—')),
    ]
    story.append(_stat_table(scope_pairs, body_width=body_w))
    story.append(Spacer(1, 5 * mm))

    provenance = task.get('provenance') or {}
    if provenance:
        story.append(_SectionHeader('Object Provenance', body_w))
        story.append(Spacer(1, 3 * mm))

        orbit = provenance.get('orbit') or {}
        orbit_parts = []
        if orbit.get('apogee_km') is not None:
            orbit_parts.append(f"{_fmt_val(orbit['apogee_km'])} km apogee")
        if orbit.get('perigee_km') is not None:
            orbit_parts.append(f"{_fmt_val(orbit['perigee_km'])} km perigee")
        if orbit.get('inclination_degrees') is not None:
            orbit_parts.append(f"{_fmt_val(orbit['inclination_degrees'])}° inc")
        if orbit.get('period_minutes') is not None:
            orbit_parts.append(f"{_fmt_val(orbit['period_minutes'])} min period")
        orbit_str = ', '.join(orbit_parts) if orbit_parts else '—'

        prov_pairs = [
            ('Name', str(provenance.get('name') or provenance.get('object_name') or '—')),
            ('NORAD ID', str(provenance.get('norad_cat_id') or norad_id or '—')),
            ('COSPAR / Int\'l Designator', str(provenance.get('international_designator') or '—')),
            ('Status', str(provenance.get('status') or '—')),
            ('Object Class', str(provenance.get('object_class') or provenance.get('object_type') or '—')),
            ('Country of Origin', str(provenance.get('country_of_origin') or '—')),
            ('Launch Date', _fmt_date(provenance.get('launch_date') or provenance.get('date_of_launch'))),
            ('Launch Site', str(provenance.get('place_of_launch') or '—')),
            ('Orbit', orbit_str),
            ('Orbital Band', str(provenance.get('orbital_band') or '—')),
            ('UN Registered', 'Yes' if provenance.get('un_registered') is True else 'No' if provenance.get('un_registered') is False else str(provenance.get('un_registered') or '—')),
            ('Registration Number', str(provenance.get('registration_number') or '—')),
            ('Function', str(provenance.get('function') or '—')),
        ]
        story.append(_stat_table(prov_pairs, body_width=body_w))
        story.append(Spacer(1, 5 * mm))

    if chart_data:
        story.append(PageBreak())
        story.append(_SectionHeader('Observation Analytics', body_w))
        story.append(Spacer(1, 3 * mm))

        chart_configs = [
            {
                'title': 'Health Score',
                'subtitle': 'Derived health score over time (0–100)',
                'left': [{'key': 'health', 'label': 'Health Score', 'color': METRIC_COLORS['health']}],
                'right': [],
                'fill_under': True,
                'fixed_range': {'min': 0, 'max': 100},
            },
            {
                'title': 'Attitude',
                'subtitle': 'Roll, Pitch, Yaw over time',
                'left': [
                    {'key': 'roll',  'label': 'Roll (°)',  'color': METRIC_COLORS['roll']},
                    {'key': 'pitch', 'label': 'Pitch (°)', 'color': METRIC_COLORS['pitch']},
                    {'key': 'yaw',   'label': 'Yaw (°)',   'color': METRIC_COLORS['yaw']},
                ],
                'right': [],
                'fill_under': False,
                'flags': [{'key': 'isUnstable', 'trueColor': '#e74c3c', 'trueLabel': 'Unstable', 'trueOnly': True, 'style': 'line'}],
            },
            {
                'title': 'Thermal',
                'subtitle': 'Surface temperature and variance',
                'left': [{'key': 'temp', 'label': 'Surface Temp (K)', 'color': METRIC_COLORS['temp']}],
                'right': [{'key': 'tempVariance', 'label': 'Variance 30d', 'color': METRIC_COLORS['tempVariance']}],
                'fill_under': True,
                'flags': [{'key': 'thermalAnomaly', 'trueColor': '#e74c3c', 'trueLabel': 'Anomaly', 'trueOnly': True, 'style': 'line'}],
            },
            {
                'title': 'Material Signature',
                'subtitle': 'Reflectivity index and confidence',
                'left': [{'key': 'reflectivity', 'label': 'Reflectivity Index', 'color': METRIC_COLORS['reflectivity']}],
                'right': [{'key': 'materialConfidence', 'label': 'Confidence', 'color': METRIC_COLORS['confidence']}],
                'fill_under': False,
            },
            {
                'title': 'Proximity State',
                'subtitle': 'Range and relative velocity',
                'left': [{'key': 'range', 'label': 'Range (km)', 'color': METRIC_COLORS['range']}],
                'right': [{'key': 'velocity', 'label': 'Rel. Velocity (m/s)', 'color': METRIC_COLORS['velocity']}],
                'fill_under': False,
            },
            {
                'title': 'Maneuver Indicator',
                'subtitle': 'ΔV residual and confidence',
                'left': [{'key': 'deltaV', 'label': 'ΔV Residual (m/s)', 'color': METRIC_COLORS['deltaV']}],
                'right': [{'key': 'manConf', 'label': 'Confidence', 'color': METRIC_COLORS['manConf']}],
                'fill_under': False,
                'flags': [{'key': 'manFlag', 'trueColor': '#ff6b6b', 'trueLabel': 'Maneuver detected', 'trueOnly': True, 'style': 'line'}],
            },
            {
                'title': 'Orbital Decay',
                'subtitle': 'Perigee drift rate and estimated perigee altitude',
                'left': [{'key': 'drift', 'label': 'Perigee Drift (km/d)', 'color': METRIC_COLORS['drift']}],
                'right': [{'key': 'estimatedPerigee', 'label': 'Est. Perigee (km)', 'color': METRIC_COLORS['perigee']}],
                'fill_under': False,
            },
            {
                'title': 'Physical Properties',
                'subtitle': 'Estimated mass and spin rate',
                'left': [{'key': 'mass', 'label': 'Mass (kg)', 'color': METRIC_COLORS['mass']}],
                'right': [{'key': 'spin', 'label': 'Spin Rate (rpm)', 'color': METRIC_COLORS['spin']}],
                'fill_under': False,
            },
        ]

        chart_w = body_w - 4 * mm
        chart_h = 82

        for cfg in chart_configs:
            has_left = any(any(r.get(m['key']) is not None for r in chart_data) for m in cfg['left'])
            has_right = any(any(r.get(m['key']) is not None for r in chart_data) for m in cfg.get('right', []))
            if not has_left and not has_right:
                continue

            title_p = Paragraph(f'<b>{cfg["title"]}</b>', ParagraphStyle(
                'ct', fontName='Helvetica-Bold', fontSize=8.5, textColor=TEXT_DARK, leading=11))
            sub_p = Paragraph(cfg.get('subtitle', ''), ParagraphStyle(
                'cs', fontName='Helvetica', fontSize=7, textColor=TEXT_LIGHT, leading=9))

            def _legend_hex(col):
                if hasattr(col, 'hexval'):
                    return col.hexval()[2:]
                return '333333'

            all_legends = [
                Paragraph(
                    f'<font color="#{_legend_hex(m["color"])}">&#9632;</font> {m["label"]}',
                    legend_style
                )
                for m in cfg['left']
            ]
            for m in cfg.get('right', []):
                col = m['color']
                all_legends.append(
                    Paragraph(f'<font color="#{_legend_hex(col)}">&#9632;</font> {m["label"]} (right axis)', legend_style)
                )

            chart = _LineChart(
                data=chart_data,
                left_metrics=cfg['left'],
                right_metrics=cfg.get('right', []),
                fixed_range=cfg.get('fixed_range'),
                fill_under=cfg.get('fill_under', False),
                flags=cfg.get('flags', []),
                chart_width=chart_w,
                chart_height=chart_h,
            )

            card_content = [title_p, Spacer(1, 1.5 * mm), sub_p, Spacer(1, 1.5 * mm), chart]
            if all_legends:
                legend_table = Table(
                    [all_legends[:4]],
                    colWidths=[chart_w / 4] * min(4, len(all_legends)),
                    style=TableStyle([('TOPPADDING', (0,0), (-1,-1), 1), ('BOTTOMPADDING', (0,0), (-1,-1), 1)]),
                )
                card_content.append(legend_table)

            card = Table(
                [[card_content]],
                colWidths=[body_w],
                style=TableStyle([
                    ('BOX', (0, 0), (-1, -1), 0.5, RULE_GRAY),
                    ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('LEFTPADDING', (0, 0), (-1, -1), 4),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                    ('ROUNDEDCORNERS', [4, 4, 4, 4]),
                ]),
            )
            story.append(card)
            story.append(Spacer(1, 3 * mm))

    passes = task.get('passes') or []
    if passes:
        story.append(PageBreak())
        story.append(_SectionHeader('Per-Pass Breakdown', body_w))
        story.append(Spacer(1, 3 * mm))

        pass_rows = [
            [p.get('pass_id') or '—', p.get('kestrel_id') or '—',
             _fmt_dt(p.get('first_epoch')), _fmt_dt(p.get('last_epoch')),
             str(p.get('frame_count') or '—'), str(p.get('sunlit_frames') or '—')]
            for p in passes
        ]
        col_w = body_w / 6
        story.append(_make_table(
            ['Pass ID', 'Kestrel ID', 'First Epoch', 'Last Epoch', 'Frames', 'Sunlit'],
            pass_rows,
            [col_w * 1.2, col_w * 0.9, col_w * 1.4, col_w * 1.4, col_w * 0.55, col_w * 0.55],
        ))
        story.append(Spacer(1, 5 * mm))

    deliverables = task.get('deliverables') or []
    if deliverables:
        story.append(_SectionHeader('Deliverables', body_w))
        story.append(Spacer(1, 3 * mm))
        del_rows = [
            [d.get('type') or '—', d.get('version') or '—',
             _fmt_dt(d.get('produced_at')), 'Yes' if d.get('released_to_customer') else 'No']
            for d in deliverables
        ]
        col_w = body_w / 4
        story.append(_make_table(
            ['Type', 'Version', 'Produced At', 'Released'],
            del_rows,
            [col_w * 1.5, col_w * 0.7, col_w * 1.4, col_w * 0.4],
        ))
        story.append(Spacer(1, 5 * mm))

    transitions = task.get('recent_transitions') or []
    if transitions:
        story.append(_SectionHeader('Audit Log', body_w))
        story.append(Spacer(1, 3 * mm))
        tr_rows = [
            [_fmt_dt(tr.get('occurred_at')), tr.get('from_status') or '—',
             tr.get('to_status') or '—', tr.get('actor') or '—', tr.get('note') or '']
            for tr in transitions
        ]
        col_w = body_w / 5
        story.append(_make_table(
            ['Time', 'From Status', 'To Status', 'Actor', 'Note'],
            tr_rows,
            [col_w * 1.4, col_w * 0.9, col_w * 0.9, col_w * 0.9, col_w * 0.9],
        ))

    def _add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(MID_GRAY)
        page_num = canvas.getPageNumber()
        canvas.drawRightString(W - MARGIN, MARGIN * 0.55, f'Page {page_num}')
        canvas.drawString(MARGIN, MARGIN * 0.55, f'TALON Observation Report · {task_number}')
        canvas.setStrokeColor(RULE_GRAY)
        canvas.setLineWidth(0.4)
        canvas.line(MARGIN, MARGIN * 0.75, W - MARGIN, MARGIN * 0.75)
        canvas.restoreState()

    doc.build(story, onFirstPage=_add_page_number, onLaterPages=_add_page_number)
    return buf.getvalue()
