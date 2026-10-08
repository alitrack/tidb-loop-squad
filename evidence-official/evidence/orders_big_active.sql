SELECT COUNT(*), SUM(amount) FROM squad_lab.orders_big
WHERE note_suffix4='-042' AND status='new';
