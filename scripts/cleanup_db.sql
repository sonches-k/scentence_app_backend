-- ============================================================
-- cleanup_db.sql  —  очистка и нормализация базы Scentence
--
-- Что делает:
--   1. Исправляет сломанное значение category (конкатенированное)
--   2. Умная дедупликация: 17 827 → ~7 265 записей
--      (сохраняет запись с наибольшим набором данных,
--       копирует category из сиблинга если у канонической нет)
--   3. Исправляет gender по явным паттернам в description
--   4. Добавляет категорию «Аттарная / Масляная» для аттаров
--   5. Проставляет category по brand-маппингу для ~900 ароматов без неё
--
-- Запуск:
--   docker exec -i perfume_app_backend-postgres-1 \
--     psql -U postgres -d perfume_db < scripts/cleanup_db.sql
-- ============================================================

BEGIN;

-- ────────────────────────────────────────────────────────────
-- 0. Статистика ДО (для сравнения)
-- ────────────────────────────────────────────────────────────
\echo ''
\echo '══════════════════════════════════════════'
\echo '  СТАТИСТИКА ДО ОЧИСТКИ'
\echo '══════════════════════════════════════════'
SELECT COUNT(*) AS total_perfumes FROM perfumes;
SELECT gender, COUNT(*) AS cnt FROM perfumes GROUP BY gender ORDER BY cnt DESC;
SELECT COALESCE(category, 'NULL') AS category, COUNT(*) AS cnt
  FROM perfumes GROUP BY category ORDER BY cnt DESC;

-- ────────────────────────────────────────────────────────────
-- 1. Исправить сломанный category
-- ────────────────────────────────────────────────────────────
\echo ''
\echo '── 1. Исправление конкатенированного category ──'
UPDATE perfumes
SET category = 'Селективная / Нишевая'
WHERE category = 'Селективная / Нишевая, Люкс / Элитная';
\echo 'Готово'

-- ────────────────────────────────────────────────────────────
-- 2. УМНАЯ ДЕДУПЛИКАЦИЯ
-- ────────────────────────────────────────────────────────────
\echo ''
\echo '── 2. Дедупликация (выбор канонических записей) ──'

-- 2a. Канонический id для каждой группы (name, brand).
--     Приоритет: есть category (+8) > есть summary (+4) > есть description (+2)
--     При равенстве — наименьший id.
CREATE TEMP TABLE _canonical AS
SELECT DISTINCT ON (name, brand)
  id   AS cid,
  name,
  brand
FROM perfumes
ORDER BY
  name,
  brand,
  (CASE WHEN category       IS NOT NULL THEN 8 ELSE 0 END +
   CASE WHEN review_summary IS NOT NULL THEN 4 ELSE 0 END +
   CASE WHEN description    IS NOT NULL THEN 2 ELSE 0 END) DESC,
  id ASC;

SELECT COUNT(*) AS canonical_count FROM _canonical;

-- 2b. Если у канонической нет category — взять из ближайшего сиблинга у которого есть
UPDATE perfumes AS p
SET category = src.category
FROM (
  SELECT DISTINCT ON (c.cid)
    c.cid,
    sib.category
  FROM _canonical c
  JOIN perfumes sib
    ON sib.name = c.name AND sib.brand = c.brand
  WHERE sib.category IS NOT NULL
  ORDER BY c.cid, sib.id ASC
) src
WHERE p.id = src.cid
  AND p.category IS NULL;

\echo 'Category скопирован из сиблингов'

-- 2c. Удаляем все НЕ-канонические записи
--     FK-констрейнты CASCADE удалят perfume_notes, perfume_embeddings,
--     perfume_tags и user_favorites автоматически
DELETE FROM perfumes
WHERE id NOT IN (SELECT cid FROM _canonical);

SELECT COUNT(*) AS after_dedup FROM perfumes;

DROP TABLE _canonical;

-- ────────────────────────────────────────────────────────────
-- 3. Исправить gender: только явные паттерны «унисекс» в description
-- ────────────────────────────────────────────────────────────
\echo ''
\echo '── 3. Исправление gender → унисекс ──'

WITH updated AS (
  UPDATE perfumes
  SET gender = 'унисекс'
  WHERE gender != 'унисекс'
    AND (
      description ILIKE '%унисекс-аромат%'
      OR description ILIKE '%унисекс-парфюм%'
      OR description ILIKE '%унисекс аромат%'
      OR description ILIKE '%унисекс парфюм%'
    )
  RETURNING id
)
SELECT COUNT(*) AS gender_fixed FROM updated;

-- ────────────────────────────────────────────────────────────
-- 4. Новая категория «Аттарная / Масляная» для аттаров/масляных духов
-- ────────────────────────────────────────────────────────────
\echo ''
\echo '── 4. Категория Аттарная / Масляная ──'

WITH updated AS (
  UPDATE perfumes
  SET category = 'Аттарная / Масляная'
  WHERE
    name ILIKE '%attar%'
    OR name ILIKE '%аттар%'
    OR (
      description ILIKE '%масляные духи%'
      AND brand IN ('Al Rehab', 'Afnan', 'Rasasi', 'Adarisa', 'Amouage')
    )
  RETURNING id
)
SELECT COUNT(*) AS attar_updated FROM updated;

-- ────────────────────────────────────────────────────────────
-- 5. Вывести category по brand-маппингу (для оставшихся NULL)
-- ────────────────────────────────────────────────────────────
\echo ''
\echo '── 5. Проставление category по бренду ──'

WITH updated AS (
  UPDATE perfumes
  SET category = brand_map.cat
  FROM (VALUES
    -- ── Люкс / Элитная ─────────────────────────────────────
    ('Lancome',                        'Люкс / Элитная'),
    ('Bvlgari',                        'Люкс / Элитная'),
    ('Guerlain',                       'Люкс / Элитная'),
    ('Gucci',                          'Люкс / Элитная'),
    ('Burberry',                       'Люкс / Элитная'),
    ('Calvin Klein',                   'Люкс / Элитная'),
    ('Carolina Herrera',               'Люкс / Элитная'),
    ('Donna Karan',                    'Люкс / Элитная'),
    ('Prada',                          'Люкс / Элитная'),
    ('Kenzo',                          'Люкс / Элитная'),
    ('Clinique',                       'Люкс / Элитная'),
    ('Lanvin',                         'Люкс / Элитная'),
    ('Cerruti',                        'Люкс / Элитная'),
    ('Geparlys',                       'Люкс / Элитная'),
    ('Adidas',                         'Люкс / Элитная'),
    ('Dolce Gabbana',                  'Люкс / Элитная'),
    ('Thierry Mugler',                 'Люкс / Элитная'),
    ('Chanel',                         'Люкс / Элитная'),
    ('Christian Dior',                 'Люкс / Элитная'),
    ('Dior',                           'Люкс / Элитная'),
    ('Givenchy',                       'Люкс / Элитная'),
    ('Versace',                        'Люкс / Элитная'),
    ('Giorgio Armani',                 'Люкс / Элитная'),
    ('Armani',                         'Люкс / Элитная'),
    ('Yves Saint Laurent',             'Люкс / Элитная'),
    ('Davidoff',                       'Люкс / Элитная'),
    ('Cartier',                        'Люкс / Элитная'),
    ('Balenciaga',                     'Люкс / Элитная'),
    ('Balmain',                        'Люкс / Элитная'),
    ('Valentino',                      'Люкс / Элитная'),
    ('Paco Rabanne',                   'Люкс / Элитная'),
    ('Jean Paul Gaultier',             'Люкс / Элитная'),
    ('Marc Jacobs',                    'Люкс / Элитная'),
    ('Tom Ford',                       'Люкс / Элитная'),
    ('Cacharel',                       'Люкс / Элитная'),
    ('Chloe',                          'Люкс / Элитная'),
    ('Montblanc',                      'Люкс / Элитная'),
    ('Roberto Cavalli',                'Люкс / Элитная'),
    ('Hugo Boss',                      'Люкс / Элитная'),
    ('Hermès',                         'Люкс / Элитная'),
    ('Alain Delon',                    'Люкс / Элитная'),
    ('Banderas',                       'Люкс / Элитная'),
    ('Bruno Banani',                   'Люкс / Элитная'),
    ('Albane Noble',                   'Люкс / Элитная'),
    ('Ulric de Varens',                'Люкс / Элитная'),
    ('Bentley',                        'Люкс / Элитная'),
    ('Nautica',                        'Люкс / Элитная'),
    ('Brut',                           'Люкс / Элитная'),
    ('Apple Parfums',                  'Люкс / Элитная'),
    ('Alain Aregon',                   'Люкс / Элитная'),
    ('Dilis',                          'Люкс / Элитная'),
    ('Delta Parfum',                   'Люкс / Элитная'),
    ('Escada',                         'Люкс / Элитная'),
    ('Pierre Cardin',                  'Люкс / Элитная'),
    ('Tonino Lamborghini',             'Люкс / Элитная'),
    ('Jo Malone',                      'Люкс / Элитная'),
    ('Desigual',                       'Люкс / Элитная'),
    ('Ed Hardy',                       'Люкс / Элитная'),
    ('Evaflor',                        'Люкс / Элитная'),
    ('Leonard',                        'Люкс / Элитная'),
    ('Bebe',                           'Люкс / Элитная'),
    ('Tocca',                          'Люкс / Элитная'),
    ('Balenciaga',                     'Люкс / Элитная'),
    ('Stefano Ricci',                  'Люкс / Элитная'),
    ('Escada',                         'Люкс / Элитная'),
    ('Salvatore Ferragamo',            'Люкс / Элитная'),
    ('Nina Ricci',                     'Люкс / Элитная'),
    ('Loewe',                          'Люкс / Элитная'),
    ('Lacoste',                        'Люкс / Элитная'),
    ('Issey Miyake',                   'Люкс / Элитная'),
    ('Hermes',                         'Люкс / Элитная'),
    ('Dkny',                           'Люкс / Элитная'),
    ('DKNY',                           'Люкс / Элитная'),
    ('Dolce & Gabbana',                'Люкс / Элитная'),
    ('Elie Saab',                      'Люкс / Элитная'),
    ('Gianni Versace',                 'Люкс / Элитная'),
    ('Emporio Armani',                 'Люкс / Элитная'),
    ('Azzaro',                         'Люкс / Элитная'),
    ('Bulgari',                        'Люкс / Элитная'),
    ('Paco',                           'Люкс / Элитная'),
    -- ── Селективная / Нишевая ──────────────────────────────
    ('Amouage',                        'Селективная / Нишевая'),
    ('Clive Christian',                'Селективная / Нишевая'),
    ('Thameen',                        'Селективная / Нишевая'),
    ('Police',                         'Селективная / Нишевая'),
    ('Micallef',                       'Селективная / Нишевая'),
    ('Ella K',                         'Селективная / Нишевая'),
    ('Evody Parfums',                  'Селективная / Нишевая'),
    ('Parle Moi de Parfum',            'Селективная / Нишевая'),
    ('PantheonRoma',                   'Селективная / Нишевая'),
    ('CnR Create',                     'Селективная / Нишевая'),
    ('CnR_Create',                     'Селективная / Нишевая'),
    ('Byredo',                         'Селективная / Нишевая'),
    ('Byredo Parfums',                 'Селективная / Нишевая'),
    ('Annick Goutal',                  'Селективная / Нишевая'),
    ('Bond No 9',                      'Селективная / Нишевая'),
    ('M.INT',                          'Селективная / Нишевая'),
    ('Binet Papillon',                 'Селективная / Нишевая'),
    ('Giardino Benessere',             'Селективная / Нишевая'),
    ('Coquillete',                     'Селективная / Нишевая'),
    ('Schwarzlose Berlin',             'Селективная / Нишевая'),
    ('Acqua Delle Langhe',             'Селективная / Нишевая'),
    ('Comme Des Garcons',              'Селективная / Нишевая'),
    ('Damien Bash',                    'Селективная / Нишевая'),
    ('Parfums Berdoues',               'Селективная / Нишевая'),
    ('Parfums et Senteurs du Pays Basque', 'Селективная / Нишевая'),
    ('Monotheme',                      'Селективная / Нишевая'),
    ('Gilles_Cantuel',                 'Селективная / Нишевая'),
    ('Ortigia Sicilia',                'Селективная / Нишевая'),
    ('Giorgio Monti',                  'Селективная / Нишевая'),
    -- ── Восточная / Арабская ───────────────────────────────
    ('Afnan',                          'Восточная / Арабская'),
    ('Rasasi',                         'Восточная / Арабская'),
    ('Al Rehab',                       'Восточная / Арабская'),
    ('Rayhaan',                        'Восточная / Арабская'),
    ('Noran Perfumes',                 'Восточная / Арабская'),
    ('Positive Parfum',                'Восточная / Арабская')
  ) AS brand_map(brand, cat)
  WHERE perfumes.brand = brand_map.brand
    AND perfumes.category IS NULL
  RETURNING id
)
SELECT COUNT(*) AS brand_category_updated FROM updated;

-- ────────────────────────────────────────────────────────────
-- 6. Статистика ПОСЛЕ
-- ────────────────────────────────────────────────────────────
COMMIT;

\echo ''
\echo '══════════════════════════════════════════'
\echo '  СТАТИСТИКА ПОСЛЕ ОЧИСТКИ'
\echo '══════════════════════════════════════════'
SELECT COUNT(*) AS total_perfumes FROM perfumes;
SELECT gender, COUNT(*) AS cnt FROM perfumes GROUP BY gender ORDER BY cnt DESC;
SELECT COALESCE(category, 'NULL') AS category, COUNT(*) AS cnt
  FROM perfumes GROUP BY category ORDER BY cnt DESC;
SELECT COUNT(*) AS with_summary   FROM perfumes WHERE review_summary IS NOT NULL;
SELECT COUNT(*) AS with_embedding FROM perfume_embeddings;
