package autotest.tko;

import java.util.Map;

import autotest.common.ui.MultiListSelectPresenter.Item;

public abstract class ParameterizedField extends HeaderField {
    private static final ParameterizedField[] prototypes = new ParameterizedField[] {
        // add all ParameterizedField subclasses here.  these instances should never escape. 
        new MachineLabelField(),
    };

    private int fieldNumber;

    protected ParameterizedField() {
        super("", "");
    }

    public static ParameterizedField fromSqlName(String sqlName) {
        ParameterizedField prototype = getPrototype(sqlName);
        ParameterizedField newField = prototype.freshInstance();
        newField.initializeFromSqlName(sqlName);
        return newField;
    }
    
    private static ParameterizedField getPrototype(String sqlName) {
        for (ParameterizedField prototype : prototypes) {
            if (sqlName.startsWith(prototype.getBaseSqlName())) {
                return prototype;
            }
        }
        
        throw new IllegalArgumentException("Failed to parse header " + sqlName);
    }

    private void initializeFromSqlName(String sqlName) {
        assert sqlName.startsWith(getBaseSqlName());

        String numberString = sqlName.substring(getBaseSqlName().length());
        try {
            fieldNumber = Integer.valueOf(numberString);
        } catch (NumberFormatException exc) {
            throw new IllegalArgumentException("Failed to parse number for header " + sqlName);
        }

        this.name = getBaseName() + " " + numberString;
        this.sqlName = getBaseSqlName() + numberString;
    }

    public int getFieldNumber() {
        return fieldNumber;
    }

    /**
     * Parameterized fields create generated items rather than regular items.
     */
    @Override
    public Item getItem() {
        return Item.createGeneratedItem(getName(), getSqlName());
    }

    public static Item getGenerator(String baseSqlName) {
        ParameterizedField prototype = getPrototype(baseSqlName);
        return Item.createGenerator(prototype.getBaseName() + "...", prototype.getBaseSqlName());
    }

    @Override
    public void addHistoryArguments(Map<String, String> arguments) {
        arguments.put(getSqlName(), getValue());
    }

    public abstract String getBaseSqlName();
    protected abstract String getBaseName();

    public abstract String getValue();
    public abstract void setValue(String value);
    
    protected abstract ParameterizedField freshInstance();
}
