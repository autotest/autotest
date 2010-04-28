package autotest.tko;


public class IterationAttributeField extends AttributeField {
    public static final String TYPE_NAME = "Iteration attribute";

    @Override
    protected ParameterizedField freshInstance() {
        return new IterationAttributeField();
    }

    @Override
    public String getTypeName() {
        return TYPE_NAME;
    }
    
    @Override
    protected String getFieldParameterName() {
        return "iteration_attribute_fields";
    }

    @Override
    public String getBaseSqlName() {
        return "iteration_attribute_";
    }
}
