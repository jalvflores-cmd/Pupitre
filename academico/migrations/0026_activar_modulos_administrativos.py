from django.db import migrations


def activar(apps, schema_editor):
    Establecimiento = apps.get_model("academico", "Establecimiento")
    for est in Establecimiento.objects.all():
        modulos = list(est.modulos or [])
        cambio = False
        for codigo in ("asistencia_personal", "sep"):
            if codigo not in modulos:
                modulos.append(codigo)
                cambio = True
        if cambio:
            est.modulos = modulos
            est.save(update_fields=["modulos"])


class Migration(migrations.Migration):
    dependencies = [("academico", "0025_asistencia_personal_y_pme")]
    operations = [migrations.RunPython(activar, migrations.RunPython.noop)]
