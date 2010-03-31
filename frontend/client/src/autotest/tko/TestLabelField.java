package autotest.tko;

public class TestLabelField extends LabelField {
    public static final String TYPE_NAME = "Test label";

    @Override
    protected ParameterizedField freshInstance() {
        return new TestLabelField();
    }

    @Override
    protected String getBaseSqlName() {
        return "test_label_";
    }

    @Override
    protected String getFieldParameterName() {
        return "test_label_fields";
    }

    @Override
    public String getTypeName() {
        return TYPE_NAME;
    }

}
