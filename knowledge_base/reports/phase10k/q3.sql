.mode list
.separator " | "
.print == paddle=yes on manual family (all models)
select m.name, v.id, v.name, v.transmission, q.paddle_shifters from v_variant_canonical_q q join variant v on v.id=q.id join model m on m.id=v.model_id where q.paddle_shifters in (1,'1') and v.transmission in ('Manual','iMT') order by 1,2;
.print == cruise=yes on CNG (Exter, Aura, Grand i10 Nios, Tigor, Nexon, Tiago)
select m.name, v.id, v.name, p.fuel_type, q.cruise_control from v_variant_canonical_q q join variant v on v.id=q.id join model m on m.id=v.model_id join powertrain p on p.id=v.powertrain_id where q.cruise_control in (1,'1') and p.fuel_type='CNG' and m.name in ('Exter','Aura','Grand i10 Nios','Tigor','Nexon','Tiago') order by 1,2;
.print == cruise on manual: Taigun, Virtus, Kushaq, Slavia
select m.name, v.id, v.name, v.transmission, q.cruise_control from v_variant_canonical_q q join variant v on v.id=q.id join model m on m.id=v.model_id where m.name in ('Taigun','Virtus','Kushaq','Slavia') and v.transmission='Manual' order by 1,2;
.print == cruise on auto: Gravite, Victoris
select m.name, v.id, v.name, v.transmission, q.cruise_control from v_variant_canonical_q q join variant v on v.id=q.id join model m on m.id=v.model_id where m.name in ('Gravite','Victoris') and v.transmission not in ('Manual') order by 1,2;
.print == Venue cruise
select m.name, v.id, v.name, p.fuel_type, v.transmission, q.cruise_control from v_variant_canonical_q q join variant v on v.id=q.id join model m on m.id=v.model_id join powertrain p on p.id=v.powertrain_id where m.name='Venue' and q.cruise_control in (1,'1') order by 2;
.print == Aura wireless and cruise
select m.name, v.id, v.name, p.fuel_type, v.transmission, q.wireless_charging, q.cruise_control from v_variant_canonical_q q join variant v on v.id=q.id join model m on m.id=v.model_id join powertrain p on p.id=v.powertrain_id where m.name='Aura' order by 2;
.print == Seltos HUD on manual; Nios ESC/hill on manual
select m.name, v.id, v.name, v.transmission, q.heads_up_display from v_variant_canonical_q q join variant v on v.id=q.id join model m on m.id=v.model_id where m.name='Seltos' and q.heads_up_display in (1,'1') and v.transmission in ('Manual','iMT');
select m.name, v.id, v.name, v.transmission, q.esc, q.hill_assist, q.cruise_control from v_variant_canonical_q q join variant v on v.id=q.id join model m on m.id=v.model_id where m.name='Grand i10 Nios' order by 2;
.print == City wireless
select m.name, v.id, v.name, v.transmission, q.wireless_charging from v_variant_canonical_q q join variant v on v.id=q.id join model m on m.id=v.model_id where m.name='City' order by 2;
