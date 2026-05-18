DECLARE @as_of_date date = '2026-05-15';
-- Ganti tanggal ini jika ingin membekukan label pada cut-off date lain.

WITH cohort AS (
    SELECT DISTINCT
        m.mahasiswa_id,
        m.pendaftar_id,
        m.prodi_id,
        m.angkatan_id,
        m.subjalur_id,
        m.jenis_kelamin,
        m.kps_status
    FROM siak.dbo.mahasiswa m
    INNER JOIN pmb_v3.dbo.pendaftar pd
        ON pd.pendaftar_id = m.pendaftar_id
),
payment_summary AS (
    SELECT
        p.tagihan_id,
        MIN(
            CASE
                WHEN p.status = 1
                    THEN COALESCE(p.tanggal_bayar, p.tanggal_bank)
            END
        ) AS first_paid_datetime
    FROM siak.dbo.pembayaran p
    WHERE p.tagihan_id IS NOT NULL
    GROUP BY p.tagihan_id
),
base_tagihan AS (
    SELECT
        t.tagihan_id,
        c.mahasiswa_id,
        c.pendaftar_id,
        c.prodi_id,
        c.angkatan_id,
        c.subjalur_id,
        c.jenis_kelamin,
        c.kps_status,
        t.total_nominal,
        t.harus_bayar,
        t.waktu_berlaku,
        t.waktu_berakhir,
        t.semesterbayar_id,
        t.tahunajaran_id,
        t.jenispembayaran_id,
        ps.first_paid_datetime,
        CASE
            WHEN ps.first_paid_datetime IS NOT NULL
                 AND CAST(ps.first_paid_datetime AS date) <= t.waktu_berakhir THEN 0
            WHEN ps.first_paid_datetime IS NOT NULL
                 AND CAST(ps.first_paid_datetime AS date) > t.waktu_berakhir THEN 1
            WHEN ps.first_paid_datetime IS NULL
                 AND t.waktu_berakhir < @as_of_date THEN 1
            ELSE NULL
        END AS is_terlambat
    FROM siak.dbo.tagihan t
    INNER JOIN cohort c
        ON c.mahasiswa_id = t.mahasiswa_id
    LEFT JOIN payment_summary ps
        ON ps.tagihan_id = t.tagihan_id
),
base_labeled AS (
    SELECT *
    FROM base_tagihan
    WHERE is_terlambat IS NOT NULL
)
SELECT
    bl.tagihan_id,
    CONCAT('Mahasiswa ', FORMAT(DENSE_RANK() OVER (ORDER BY bl.mahasiswa_id), '0000')) AS mahasiswa,
    bl.waktu_berakhir AS tanggal_jatuh_tempo,

    bl.is_terlambat,

    CAST(bl.total_nominal AS decimal(18,2)) AS nominal_tagihan,
    CAST(bl.harus_bayar AS decimal(18,2)) AS nominal_harus_bayar,

    jp.jenis_pembayaran,
    ta.tahun_ajaran,
    sb.semester AS semester_tagihan,
    sb.jenis_semester,
    MONTH(bl.waktu_berakhir) AS bulan_jatuh_tempo,

    ag.angkatan,
    pr.kode_prodi,
    pr.nama_prodi,

    jl.nama_jalur AS jalur_masuk,
    sj.nama_subjalur AS subjalur_masuk,

    COALESCE(NULLIF(LTRIM(RTRIM(bl.jenis_kelamin)), ''), 'Unknown') AS jenis_kelamin,

    COALESCE(NULLIF(LTRIM(RTRIM(smp.statusmhs)), ''), 'Unknown') AS statusmhs_periode,
    CASE WHEN smp.statusmhs_id IS NULL THEN 1 ELSE 0 END AS is_statusmhs_periode_missing,

    CASE
        WHEN bl.kps_status = 1 THEN 'Ya'
        WHEN bl.kps_status = 0 THEN 'Tidak'
        ELSE 'Unknown'
    END AS kps_status,
    CASE WHEN bl.kps_status IS NULL THEN 1 ELSE 0 END AS is_kps_status_missing,

    pd.jumlah_saudara,
    CASE WHEN pd.jumlah_saudara IS NULL THEN 1 ELSE 0 END AS is_jumlah_saudara_missing,

    CASE kk.penghasilan_ortu
        WHEN 1 THEN '1 Juta'
        WHEN 2 THEN '2 Juta'
        WHEN 3 THEN '3 Juta'
        WHEN 4 THEN '4 Juta'
        WHEN 5 THEN '5 Juta'
        WHEN 6 THEN 'Diatas 5 Juta'
        ELSE 'Unknown'
    END AS penghasilan_ortu_label,
    CASE WHEN kk.penghasilan_ortu IS NULL THEN 1 ELSE 0 END AS is_penghasilan_ortu_missing,

    CASE kk.pendidikan_ayah
        WHEN 1 THEN 'SD'
        WHEN 2 THEN 'SMP'
        WHEN 3 THEN 'SMA'
        WHEN 4 THEN 'S1'
        WHEN 5 THEN 'S2'
        ELSE 'Tidak diisi'
    END AS pendidikan_ayah_label,
    CASE WHEN kk.pendidikan_ayah IS NULL THEN 1 ELSE 0 END AS is_pendidikan_ayah_missing,

    CASE kk.pendidikan_ibu
        WHEN 1 THEN 'SD'
        WHEN 2 THEN 'SMP'
        WHEN 3 THEN 'SMA'
        WHEN 4 THEN 'S1'
        WHEN 5 THEN 'S2'
        ELSE 'Tidak diisi'
    END AS pendidikan_ibu_label,
    CASE WHEN kk.pendidikan_ibu IS NULL THEN 1 ELSE 0 END AS is_pendidikan_ibu_missing,

    COALESCE(pa.pekerjaan, 'Unknown') AS pekerjaan_ayah,
    CASE WHEN kk.pekerjaan_ayah IS NULL THEN 1 ELSE 0 END AS is_pekerjaan_ayah_missing,

    COALESCE(pi.pekerjaan, 'Unknown') AS pekerjaan_ibu,
    CASE WHEN kk.pekerjaan_ibu IS NULL THEN 1 ELSE 0 END AS is_pekerjaan_ibu_missing,

    COALESCE(hist.prev_tagihan_count, 0) AS prev_tagihan_count,
    COALESCE(hist.prev_late_count, 0) AS prev_late_count,
    COALESCE(hist.prev_late_ratio, 0.0000) AS prev_late_ratio,
    COALESCE(hist.prev_cicilan_count, 0) AS prev_cicilan_count,
    COALESCE(hist.prev_cicilan_ratio, 0.0000) AS prev_cicilan_ratio

FROM base_labeled bl
INNER JOIN pmb_v3.dbo.pendaftar pd
    ON pd.pendaftar_id = bl.pendaftar_id
LEFT JOIN pmb_v3.dbo.keluarga kk
    ON kk.keluarga_id = pd.keluarga_id
LEFT JOIN pmb_v3.dbo.vw_pekerjaan pa
    ON pa.pekerjaan_id = kk.pekerjaan_ayah
LEFT JOIN pmb_v3.dbo.vw_pekerjaan pi
    ON pi.pekerjaan_id = kk.pekerjaan_ibu

INNER JOIN siak.dbo.jenis_pembayaran jp
    ON jp.jenispembayaran_id = bl.jenispembayaran_id
LEFT JOIN siak.dbo.tahun_ajaran ta
    ON ta.tahunajaran_id = bl.tahunajaran_id
LEFT JOIN siak.dbo.semester_bayar sb
    ON sb.semesterbayar_id = bl.semesterbayar_id
LEFT JOIN siak.dbo.angkatan ag
    ON ag.angkatan_id = bl.angkatan_id
LEFT JOIN siak.dbo.prodi pr
    ON pr.prodi_id = bl.prodi_id
LEFT JOIN siak.dbo.subjalur sj
    ON sj.subjalur_id = bl.subjalur_id
LEFT JOIN siak.dbo.jalur jl
    ON jl.jalur_id = sj.jalur_id

OUTER APPLY (
    SELECT TOP 1
        sm.statusmhs_id,
        sm.statusmhs
    FROM siak.dbo.statusmhs sm
    WHERE sm.mahasiswa_id = bl.mahasiswa_id
      AND sm.tahunajaran_id = bl.tahunajaran_id
      AND sm.semesterbayar_id = bl.semesterbayar_id
      AND sm.status = 1
    ORDER BY sm.statusmhs_id DESC
) smp

OUTER APPLY (
    SELECT
        prev_stats.prev_tagihan_count,
        prev_stats.prev_late_count,
        CAST(
            COALESCE(
                prev_stats.prev_late_count * 1.0 / NULLIF(prev_stats.prev_tagihan_count, 0),
                0
            ) AS decimal(10,4)
        ) AS prev_late_ratio,
        prev_stats.prev_cicilan_count,
        CAST(
            COALESCE(
                prev_stats.prev_cicilan_count * 1.0 / NULLIF(prev_stats.prev_tagihan_count, 0),
                0
            ) AS decimal(10,4)
        ) AS prev_cicilan_ratio
    FROM (
        SELECT
            COUNT(*) AS prev_tagihan_count,
            SUM(CASE WHEN prev.prev_label = 0 THEN 1 ELSE 0 END) AS prev_late_count,
            SUM(CASE WHEN prev.had_cicilan_before_current = 1 THEN 1 ELSE 0 END) AS prev_cicilan_count
        FROM (
            SELECT
                pt.tagihan_id,
                CASE
                    WHEN psp.first_paid_datetime IS NOT NULL
                         AND CAST(psp.first_paid_datetime AS date) <= pt.waktu_berakhir THEN 1
                    ELSE 0
                END AS prev_label,
                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM siak.dbo.pembayaran px
                        WHERE px.tagihan_id = pt.tagihan_id
                          AND px.status = 1
                          AND px.status_pembayaran = 'Cicilan'
                          AND CAST(COALESCE(px.tanggal_bayar, px.tanggal_bank) AS date) <= bl.waktu_berakhir
                    ) THEN 1
                    ELSE 0
                END AS had_cicilan_before_current
            FROM siak.dbo.tagihan pt
            LEFT JOIN payment_summary psp
                ON psp.tagihan_id = pt.tagihan_id
            WHERE pt.mahasiswa_id = bl.mahasiswa_id
              AND pt.waktu_berakhir < bl.waktu_berakhir
        ) prev
    ) prev_stats
) hist

WHERE jp.jenis_pembayaran IN ('Semester', 'SPT', 'Cuti')

ORDER BY
    bl.waktu_berakhir,
    bl.mahasiswa_id,
    bl.tagihan_id;
