-- ============================================================
-- The Mentalist S01 — вставка данных для тестирования плеера
-- Выполнять по порядку через Adminer
-- ============================================================

-- IDs (сгенерированы скриптом загрузки):
-- media_item_id:  14f18345-5b71-4214-95fd-c338f08db14b
-- user_id:        2ffb4ad6-e2ce-4232-a857-db71c08eced1
-- task_id:        b62209f2-e924-4fcd-80de-b79870986a1e

-- 1. MediaItem
INSERT INTO media_items (id, kp_id, kp_type, title, original_title, year, poster_url, overview, rating_kp, genres, raw, updated_at)
VALUES (
    '14f18345-5b71-4214-95fd-c338f08db14b',
    395999,
    'tv',
    'Менталист',
    'The Mentalist',
    2008,
    'https://st.kp.yandex.net/images/film_iphone/iphone360_395999.jpg',
    'Патрик Джейн — бывший экстрасенс-шарлатан, который после трагической гибели семьи начинает помогать полиции Калифорнии в раскрытии преступлений.',
    8.2,
    ARRAY['детектив', 'драма', 'комедия', 'криминал'],
    '{}'::jsonb,
    NOW()
)
ON CONFLICT (kp_id) DO UPDATE SET title = 'Менталист', updated_at = NOW();

-- 2. TorrentRelease (заглушка, нужна для FK в tasks)
INSERT INTO torrent_releases (id, media_item_id, source, tracker, title, info_hash, size_bytes, seeders, leechers, quality, voiceover, magnet, fetched_at)
VALUES (
    '70ab5654-8f8f-481a-89ae-a95173382f11',
    '14f18345-5b71-4214-95fd-c338f08db14b',
    'manual',
    'manual',
    'The Mentalist S01 WEB-DL [teko]',
    'manual_000000000000000000000000000000',
    16500000000,
    0, 0,
    'WEB-DL',
    'teko',
    NULL,
    NOW()
)
ON CONFLICT (media_item_id, info_hash) DO NOTHING;

-- 3. Task (завершённая задача)
INSERT INTO tasks (id, user_id, media_item_id, torrent_release_id, worker_id, status, priority, attempts, max_attempts, reserved_bytes, progress_pct, speed_bps, stage, error, lease_expires_at, created_at, updated_at)
VALUES (
    'b62209f2-e924-4fcd-80de-b79870986a1e',
    '2ffb4ad6-e2ce-4232-a857-db71c08eced1',
    '14f18345-5b71-4214-95fd-c338f08db14b',
    '70ab5654-8f8f-481a-89ae-a95173382f11',
    NULL,
    'completed',
    0, 0, 3,
    0, 100, 0,
    NULL, NULL, NULL,
    NOW(), NOW()
);

-- 4. LibraryItem
INSERT INTO library_items (id, user_id, media_item_id, source_task_id, status, created_at)
VALUES (
    '830602d4-e288-48bc-86f7-6986f9648d3f',
    '2ffb4ad6-e2ce-4232-a857-db71c08eced1',
    '14f18345-5b71-4214-95fd-c338f08db14b',
    'b62209f2-e924-4fcd-80de-b79870986a1e',
    'ready',
    NOW()
)
ON CONFLICT (user_id, media_item_id) DO NOTHING;

-- 5. TaskFiles (23 эпизода)
INSERT INTO task_files (id, task_id, path, size_bytes, s3_key, status, season, episode, uploaded_at) VALUES
('373045a4-e220-49b1-872f-a7d768ec4c6e', 'b62209f2-e924-4fcd-80de-b79870986a1e', 's01e01_Pilot.avi', 745175040, 'users/2ffb4ad6-e2ce-4232-a857-db71c08eced1/14f18345-5b71-4214-95fd-c338f08db14b/s01e01_Pilot.avi', 'uploaded', 1, 1, NOW()),
('cf4a5f9e-0c93-4ce7-9733-c66305427c28', 'b62209f2-e924-4fcd-80de-b79870986a1e', 's01e02_Red.Hair.and.Silver.Tape.avi', 718755840, 'users/2ffb4ad6-e2ce-4232-a857-db71c08eced1/14f18345-5b71-4214-95fd-c338f08db14b/s01e02_Red.Hair.and.Silver.Tape.avi', 'uploaded', 1, 2, NOW()),
('80be3581-d319-4d16-9626-f7d4aa2c1336', 'b62209f2-e924-4fcd-80de-b79870986a1e', 's01e03_Red.Tide.avi', 718700544, 'users/2ffb4ad6-e2ce-4232-a857-db71c08eced1/14f18345-5b71-4214-95fd-c338f08db14b/s01e03_Red.Tide.avi', 'uploaded', 1, 3, NOW()),
('0964a911-8b4b-4d30-97b8-2dba244f900d', 'b62209f2-e924-4fcd-80de-b79870986a1e', 's01e04_Ladies.in.Red.avi', 715937792, 'users/2ffb4ad6-e2ce-4232-a857-db71c08eced1/14f18345-5b71-4214-95fd-c338f08db14b/s01e04_Ladies.in.Red.avi', 'uploaded', 1, 4, NOW()),
('216fdc1f-64f0-43ae-a23e-73ef4ed9a90c', 'b62209f2-e924-4fcd-80de-b79870986a1e', 's01e05_Redwood.avi', 722896896, 'users/2ffb4ad6-e2ce-4232-a857-db71c08eced1/14f18345-5b71-4214-95fd-c338f08db14b/s01e05_Redwood.avi', 'uploaded', 1, 5, NOW()),
('02ab58c4-39ab-41ed-8f5a-b3a55b07d280', 'b62209f2-e924-4fcd-80de-b79870986a1e', 's01e06_Red-Handed.avi', 725694464, 'users/2ffb4ad6-e2ce-4232-a857-db71c08eced1/14f18345-5b71-4214-95fd-c338f08db14b/s01e06_Red-Handed.avi', 'uploaded', 1, 6, NOW()),
('32f83e93-59af-4a59-a96f-eff4102be4f1', 'b62209f2-e924-4fcd-80de-b79870986a1e', 's01e07_Seeing.Red.avi', 724815872, 'users/2ffb4ad6-e2ce-4232-a857-db71c08eced1/14f18345-5b71-4214-95fd-c338f08db14b/s01e07_Seeing.Red.avi', 'uploaded', 1, 7, NOW()),
('2a8127e5-9443-4200-8581-8557989c5f89', 'b62209f2-e924-4fcd-80de-b79870986a1e', 's01e08_The.Thin.Red.Line.avi', 695631872, 'users/2ffb4ad6-e2ce-4232-a857-db71c08eced1/14f18345-5b71-4214-95fd-c338f08db14b/s01e08_The.Thin.Red.Line.avi', 'uploaded', 1, 8, NOW()),
('bd9d3820-2804-48cb-ac19-7818f15672b7', 'b62209f2-e924-4fcd-80de-b79870986a1e', 's01e09_Flame.Red.avi', 725786624, 'users/2ffb4ad6-e2ce-4232-a857-db71c08eced1/14f18345-5b71-4214-95fd-c338f08db14b/s01e09_Flame.Red.avi', 'uploaded', 1, 9, NOW()),
('c8c92c9f-dab3-4ac1-a24b-c40e1ad846fa', 'b62209f2-e924-4fcd-80de-b79870986a1e', 's01e10_Red.Brick.and.Ivy.avi', 697845760, 'users/2ffb4ad6-e2ce-4232-a857-db71c08eced1/14f18345-5b71-4214-95fd-c338f08db14b/s01e10_Red.Brick.and.Ivy.avi', 'uploaded', 1, 10, NOW()),
('03731c72-7367-4825-9c05-5ce154e43b0b', 'b62209f2-e924-4fcd-80de-b79870986a1e', 's01e11_Red.John''s.Friends.avi', 726704128, 'users/2ffb4ad6-e2ce-4232-a857-db71c08eced1/14f18345-5b71-4214-95fd-c338f08db14b/s01e11_Red.John''s.Friends.avi', 'uploaded', 1, 11, NOW()),
('c3bc7d48-fb4d-4555-9d78-9420bbf607fe', 'b62209f2-e924-4fcd-80de-b79870986a1e', 's01e12_Red.Rum.avi', 699711488, 'users/2ffb4ad6-e2ce-4232-a857-db71c08eced1/14f18345-5b71-4214-95fd-c338f08db14b/s01e12_Red.Rum.avi', 'uploaded', 1, 12, NOW()),
('7b9636f1-3176-423c-a101-87771ebd1e56', 'b62209f2-e924-4fcd-80de-b79870986a1e', 's01e13_Paint.It.Red.avi', 706119680, 'users/2ffb4ad6-e2ce-4232-a857-db71c08eced1/14f18345-5b71-4214-95fd-c338f08db14b/s01e13_Paint.It.Red.avi', 'uploaded', 1, 13, NOW()),
('bb14d764-f575-4f08-8ed5-cd28a776697c', 'b62209f2-e924-4fcd-80de-b79870986a1e', 's01e14_Crimson.Casanova.avi', 725696512, 'users/2ffb4ad6-e2ce-4232-a857-db71c08eced1/14f18345-5b71-4214-95fd-c338f08db14b/s01e14_Crimson.Casanova.avi', 'uploaded', 1, 14, NOW()),
('67b12b9d-54db-4bb9-b21a-c7804bf002a3', 'b62209f2-e924-4fcd-80de-b79870986a1e', 's01e15_Scarlett.Fever.avi', 720416768, 'users/2ffb4ad6-e2ce-4232-a857-db71c08eced1/14f18345-5b71-4214-95fd-c338f08db14b/s01e15_Scarlett.Fever.avi', 'uploaded', 1, 15, NOW()),
('9b115689-ffd7-4a27-aabf-4cc19488fb6f', 'b62209f2-e924-4fcd-80de-b79870986a1e', 's01e16_Bloodshot.avi', 726964224, 'users/2ffb4ad6-e2ce-4232-a857-db71c08eced1/14f18345-5b71-4214-95fd-c338f08db14b/s01e16_Bloodshot.avi', 'uploaded', 1, 16, NOW()),
('d5104d74-6351-422e-9871-0d43ec1b7b61', 'b62209f2-e924-4fcd-80de-b79870986a1e', 's01e17_Carnelian,Inc..avi', 702697472, 'users/2ffb4ad6-e2ce-4232-a857-db71c08eced1/14f18345-5b71-4214-95fd-c338f08db14b/s01e17_Carnelian,Inc..avi', 'uploaded', 1, 17, NOW()),
('8892db78-7e96-4e0b-8dcc-7d31c894d0f7', 'b62209f2-e924-4fcd-80de-b79870986a1e', 's01e18_Russet.Potatoes.avi', 704155648, 'users/2ffb4ad6-e2ce-4232-a857-db71c08eced1/14f18345-5b71-4214-95fd-c338f08db14b/s01e18_Russet.Potatoes.avi', 'uploaded', 1, 18, NOW()),
('18f53102-b459-48ee-8bf7-f0898bc14525', 'b62209f2-e924-4fcd-80de-b79870986a1e', 's01e19_A.Dozen.Red.Roses.avi', 703309824, 'users/2ffb4ad6-e2ce-4232-a857-db71c08eced1/14f18345-5b71-4214-95fd-c338f08db14b/s01e19_A.Dozen.Red.Roses.avi', 'uploaded', 1, 19, NOW()),
('1f3857ad-2412-4c2a-8623-5dae34a675c5', 'b62209f2-e924-4fcd-80de-b79870986a1e', 's01e20_Red.Sauce.avi', 719335424, 'users/2ffb4ad6-e2ce-4232-a857-db71c08eced1/14f18345-5b71-4214-95fd-c338f08db14b/s01e20_Red.Sauce.avi', 'uploaded', 1, 20, NOW()),
('8ff6436e-03fd-47e9-bcbd-c260acab0d3a', 'b62209f2-e924-4fcd-80de-b79870986a1e', 's01e21_Miss.Red.avi', 724582400, 'users/2ffb4ad6-e2ce-4232-a857-db71c08eced1/14f18345-5b71-4214-95fd-c338f08db14b/s01e21_Miss.Red.avi', 'uploaded', 1, 21, NOW()),
('c0270229-1c28-4ca4-811b-7e2ee79d7824', 'b62209f2-e924-4fcd-80de-b79870986a1e', 's01e22_Blood.Brothers.avi', 723095552, 'users/2ffb4ad6-e2ce-4232-a857-db71c08eced1/14f18345-5b71-4214-95fd-c338f08db14b/s01e22_Blood.Brothers.avi', 'uploaded', 1, 22, NOW()),
('6aa36f63-e54c-436d-b61e-c33a53afcaa1', 'b62209f2-e924-4fcd-80de-b79870986a1e', 's01e23_Red.John''s.Footsteps.avi', 726384640, 'users/2ffb4ad6-e2ce-4232-a857-db71c08eced1/14f18345-5b71-4214-95fd-c338f08db14b/s01e23_Red.John''s.Footsteps.avi', 'uploaded', 1, 23, NOW());

-- Готово! 23 эпизода, ~15.4 ГБ на S3