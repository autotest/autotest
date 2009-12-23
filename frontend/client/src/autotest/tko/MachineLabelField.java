package autotest.tko;


public class MachineLabelField extends LabelField {
    public static final String TYPE_NAME = "Machine label";

    @Override
    public String getTypeName() {
        return TYPE_NAME;
    }

    @Override
    protected ParameterizedField freshInstance() {
        return new MachineLabelField();
    }

    @Override
    protected String getFieldParameterName() {
        return "machine_label_fields";
    }

    @Override
    public String getBaseSqlName() {
        return "machine_label_";
    }
}
