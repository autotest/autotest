package autotest.tko;


public class JobKeyvalField extends AttributeField {
    public static final String TYPE_NAME = "Job Keyval";

    @Override
    protected ParameterizedField freshInstance() {
        return new JobKeyvalField();
    }

    @Override
    public String getTypeName() {
        return TYPE_NAME;
    }
    
    @Override
    protected String getFieldParameterName() {
        return "job_keyval_fields";
    }

    @Override
    public String getBaseSqlName() {
        return "job_keyval_";
    }
}
