package autotest.tko;

public abstract class StringParameterizedField extends ParameterizedField {
    private String attribute;

    @Override
    public String getValue() {
        return attribute;
    }

    @Override
    public void setValue(String value) {
        attribute = value;
    }
}
