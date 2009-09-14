package autotest.tko;

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
        newField.initializedFromSqlName(sqlName);
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

    private void initializedFromSqlName(String sqlName) {
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

    public static Item getGenerator(String baseSqlName) {
        ParameterizedField prototype = getPrototype(baseSqlName);
        return Item.createGenerator(prototype.getBaseName() + "...", prototype.getBaseSqlName());
    }

    public abstract String getBaseSqlName();
    protected abstract String getBaseName();

    public abstract String getValue();
    public abstract void setValue(String value);
    
    protected abstract ParameterizedField freshInstance();
}
