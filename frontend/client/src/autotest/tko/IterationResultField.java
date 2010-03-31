package autotest.tko;


public class IterationResultField extends AttributeField {
    public static final String TYPE_NAME = "Iteration result";

    @Override
    protected ParameterizedField freshInstance() {
        return new IterationResultField();
    }

    @Override
    public String getTypeName() {
        return TYPE_NAME;
    }
    
    @Override
    protected String getFieldParameterName() {
        return "iteration_result_fields";
    }

    @Override
    public String getBaseSqlName() {
        return "iteration_result_";
    }
}
