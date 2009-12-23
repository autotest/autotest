package autotest.tko;


public class TestAttributeField extends AttributeField {
    public static final String TYPE_NAME = "Test attribute";

    @Override
    protected ParameterizedField freshInstance() {
        return new TestAttributeField();
    }

    @Override
    public String getTypeName() {
        return TYPE_NAME;
    }

    @Override
    protected String getFieldParameterName() {
        return "test_attribute_fields";
    }

    @Override
    public String getBaseSqlName() {
        return "attribute_";
    }
}
